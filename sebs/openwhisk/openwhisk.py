import json
import os
import shutil
import subprocess
from typing import cast, Dict, List, Tuple, Type

import docker

from sebs.benchmark import Benchmark
from sebs.cache import Cache
from sebs.faas import System, PersistentStorage
from sebs.faas.function import Function, ExecutionResult, Trigger
from .minio import Minio
from sebs.openwhisk.triggers import LibraryTrigger, HTTPTrigger
from sebs.utils import PROJECT_DIR, LoggingHandlers, execute
from .config import OpenWhiskConfig
from .function import OpenwhiskFunction
from ..config import SeBSConfig


class OpenWhisk(System):
    _config: OpenWhiskConfig
    storage: Minio

    def __init__(
        self,
        system_config: SeBSConfig,
        config: OpenWhiskConfig,
        cache_client: Cache,
        docker_client: docker.client,
        logger_handlers: LoggingHandlers,
    ):
        super().__init__(system_config, cache_client, docker_client)
        self._config = config
        self.logging_handlers = logger_handlers

        if self.config.resources.docker_username:
            if self.config.resources.docker_registry:
                docker_client.login(
                    username=self.config.resources.docker_username,
                    password=self.config.resources.docker_password,
                    registry=self.config.resources.docker_registry,
                )
            else:
                docker_client.login(
                    username=self.config.resources.docker_username,
                    password=self.config.resources.docker_password,
                )

    @property
    def config(self) -> OpenWhiskConfig:
        return self._config

    def get_storage(self, replace_existing: bool = False) -> PersistentStorage:
        if not hasattr(self, "storage"):
            self.storage = Minio(self.docker_client, self.cache_client, replace_existing, self._config.storageListenAddr)
            self.storage.logging_handlers = self.logging_handlers
            self.storage.start()
        else:
            self.storage.replace_existing = replace_existing
        return self.storage

    def shutdown(self) -> None:
        if hasattr(self, "storage") and self.config.shutdownStorage:
            self.storage.stop()
        if self.config.removeCluster:
            from tools.openwhisk_preparation import delete_cluster  # type: ignore

            delete_cluster()
        super().shutdown()

    @staticmethod
    def name() -> str:
        return "openwhisk"

    @staticmethod
    def typename():
        return "OpenWhisk"

    @staticmethod
    def function_type() -> "Type[Function]":
        return OpenwhiskFunction

    def get_wsk_cmd(self) -> List[str]:
        cmd = [self.config.wsk_exec]
        if self.config.wsk_bypass_security:
            cmd.append("-i")
        return cmd

    def find_image(self, repository_name, image_tag) -> bool:

        if self.config.experimentalManifest:
            try:
                # This requires enabling experimental Docker features
                # Furthermore, it's not yet supported in the Python library
                execute(f"docker manifest inspect {repository_name}:{image_tag}")
                return True
            except RuntimeError:
                return False
        else:
            try:
                # default version requires pulling for an image
                self.docker_client.images.pull(repository=repository_name, tag=image_tag)
                return True
            except docker.errors.NotFound:
                return False

    def build_base_image(
        self,
        directory: str,
        language_name: str,
        language_version: str,
        benchmark: str,
        is_cached: bool,
    ) -> bool:
        """
        When building function for the first time (according to SeBS cache),
        check if Docker image is available in the registry.
        If yes, then skip building.
        If no, then continue building.

        For every subsequent build, we rebuild image and push it to the
        registry. These are triggered by users modifying code and enforcing
        a build.
        """

        # We need to retag created images when pushing to registry other
        # than default
        registry_name = self.config.resources.docker_registry
        repository_name = self.system_config.docker_repository()
        image_tag = self.system_config.benchmark_image_tag(
            self.name(), benchmark, language_name, language_version
        )
        if registry_name is not None:
            repository_name = f"{registry_name}/{repository_name}"
        else:
            registry_name = "Docker Hub"

        # Check if we the image is already in the registry.
        if not is_cached:
            if self.find_image(repository_name, image_tag):
                self.logging.info(
                    f"Skipping building OpenWhisk package for {benchmark}, using "
                    f"Docker image {repository_name}:{image_tag} from registry: "
                    f"{registry_name}."
                )
                return False
            else:
                # image doesn't exist, let's continue
                self.logging.info(
                    f"Image {repository_name}:{image_tag} doesn't exist in the registry, "
                    f"building OpenWhisk package for {benchmark}."
                )

        build_dir = os.path.join(directory, "docker")
        os.makedirs(build_dir)
        shutil.copy(
            os.path.join(PROJECT_DIR, "docker", f"Dockerfile.run.{self.name()}.{language_name}"),
            os.path.join(build_dir, "Dockerfile"),
        )

        for fn in os.listdir(directory):
            if fn not in ("index.js", "__main__.py"):
                file = os.path.join(directory, fn)
                shutil.move(file, build_dir)

        with open(os.path.join(build_dir, ".dockerignore"), "w") as f:
            f.write("Dockerfile")

        builder_image = self.system_config.benchmark_base_images(self.name(), language_name)[
            language_version
        ]
        self.logging.info(f"Build the benchmark base image {repository_name}:{image_tag}.")
        image, _ = self.docker_client.images.build(
            tag=f"{repository_name}:{image_tag}",
            path=build_dir,
            buildargs={
                "BASE_IMAGE": builder_image,
            },
        )

        # Now push the image to the registry
        # image will be located in a private repository
        self.logging.info(
            f"Push the benchmark base image {repository_name}:{image_tag} "
            f"to registry: {registry_name}."
        )
        ret = self.docker_client.images.push(
            repository=repository_name, tag=image_tag, stream=True, decode=True
        )
        # doesn't raise an exception for some reason
        for val in ret:
            if "error" in val:
                self.logging.error(f"Failed to push the image to registry {registry_name}")
                raise RuntimeError(val)
        return True

    def package_code(
        self,
        directory: str,
        language_name: str,
        language_version: str,
        benchmark: str,
        is_cached: bool,
    ) -> Tuple[str, int]:

        # Regardless of Docker image status, we need to create .zip file
        # to allow registration of function with OpenWhisk
        self.build_base_image(directory, language_name, language_version, benchmark, is_cached)

        # We deploy Minio config in code package since this depends on local
        # deployment - it cannnot be a part of Docker image
        minio_config_path = "minioConfig.json"
        CONFIG_FILES = {
            "python": ["__main__.py", minio_config_path],
            "nodejs": ["index.js", minio_config_path],
        }
        package_config = CONFIG_FILES[language_name]

        with open(os.path.join(directory, minio_config_path), "w+") as minio_config:
            storage = cast(Minio, self.get_storage())
            minio_config_json = {
                "access_key": storage._access_key,
                "secret_key": storage._secret_key,
                "url": storage._url,
            }
            minio_config.write(json.dumps(minio_config_json))

        os.chdir(directory)
        benchmark_archive = os.path.join(directory, f"{benchmark}.zip")
        subprocess.run(
            ["zip", benchmark_archive] + package_config,
            stdout=subprocess.DEVNULL,
        )
        self.logging.info(f"Created {benchmark_archive} archive")
        bytes_size = os.path.getsize(benchmark_archive)
        self.logging.info("Zip archive size {:2f} MB".format(bytes_size / 1024.0 / 1024.0))
        return benchmark_archive, bytes_size

    def create_function(self, code_package: Benchmark, func_name: str) -> "OpenwhiskFunction":
        self.logging.info("Creating function as an action in OpenWhisk")
        try:
            actions = subprocess.run(
                [*self.get_wsk_cmd(), "action", "list"],
                stderr=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
            )
            subprocess.run(
                f"grep {func_name}".split(),
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                input=actions.stdout,
                check=True,
            )

            res = OpenwhiskFunction(func_name, code_package.benchmark, code_package.hash)
            # Update function - we don't know what version is stored
            self.update_function(res, code_package)
            self.logging.info(f"Retrieved OpenWhisk action {func_name}")

        except FileNotFoundError as e:
            self.logging.error("Could not retrieve OpenWhisk functions - is path to wsk correct?")
            raise RuntimeError(e)

        except subprocess.CalledProcessError:
            # grep will return error when there are no entries
            try:
                docker_image = self.system_config.benchmark_image_name(
                    self.name(),
                    code_package.benchmark,
                    code_package.language_name,
                    code_package.language_version,
                )
                subprocess.run(
                    [
                        *self.get_wsk_cmd(),
                        "action",
                        "create",
                        func_name,
                        "--web",
                        "true",
                        "--docker",
                        docker_image,
                        "--memory",
                        str(code_package.benchmark_config.memory),
                        code_package.code_location,
                    ],
                    stderr=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    check=True,
                )
                self.logging.info(f"Created new OpenWhisk action {func_name}")
                res = OpenwhiskFunction(func_name, code_package.benchmark, code_package.hash)
            except subprocess.CalledProcessError as e:
                self.logging.error(f"Cannot create action {func_name}.")
                raise RuntimeError(e)

        # Add LibraryTrigger to a new function
        trigger = LibraryTrigger(func_name, self.get_wsk_cmd())
        trigger.logging_handlers = self.logging_handlers
        res.add_trigger(trigger)

        return res

    def update_function(self, function: Function, code_package: Benchmark):
        docker_image = self.system_config.benchmark_image_name(
            self.name(),
            code_package.benchmark,
            code_package.language_name,
            code_package.language_version,
        )
        try:
            subprocess.run(
                [
                    *self.get_wsk_cmd(),
                    "action",
                    "update",
                    function.name,
                    "--docker",
                    docker_image,
                    "--memory",
                    str(code_package.benchmark_config.memory),
                    code_package.code_location,
                ],
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                check=True,
            )
        except FileNotFoundError as e:
            self.logging.error("Could not update OpenWhisk function - is path to wsk correct?")
            raise RuntimeError(e)

    def default_function_name(self, code_package: Benchmark) -> str:
        return (
            f"{code_package.benchmark}-{code_package.language_name}-"
            f"{code_package.language_version}"
        )

    def enforce_cold_start(self, functions: List[Function], code_package: Benchmark):
        raise NotImplementedError()

    def download_metrics(
        self,
        function_name: str,
        start_time: int,
        end_time: int,
        requests: Dict[str, ExecutionResult],
        metrics: dict,
    ):
        pass

    def create_trigger(self, function: Function, trigger_type: Trigger.TriggerType) -> Trigger:
        if trigger_type == Trigger.TriggerType.LIBRARY:
            return function.triggers(Trigger.TriggerType.LIBRARY)[0]
        elif trigger_type == Trigger.TriggerType.HTTP:
            try:
                response = subprocess.run(
                    [*self.get_wsk_cmd(), "action", "get", function.name, "--url"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
            except FileNotFoundError as e:
                self.logging.error(
                    "Could not retrieve OpenWhisk configuration - is path to wsk correct?"
                )
                raise RuntimeError(e)
            stdout = response.stdout.decode("utf-8")
            url = stdout.strip().split("\n")[-1] + ".json"
            trigger = HTTPTrigger(function.name, url)
            trigger.logging_handlers = self.logging_handlers
            function.add_trigger(trigger)
            self.cache_client.update_function(function)
            return trigger
        else:
            raise RuntimeError("Not supported!")

    def cached_function(self, function: Function):
        for trigger in function.triggers(Trigger.TriggerType.LIBRARY):
            trigger.logging_handlers = self.logging_handlers
            cast(LibraryTrigger, trigger).wsk_cmd = self.get_wsk_cmd()
        for trigger in function.triggers(Trigger.TriggerType.HTTP):
            trigger.logging_handlers = self.logging_handlers
