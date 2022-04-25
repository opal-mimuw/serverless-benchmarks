# SeBS: Serverless Benchmark Suite

**FaaS benchmarking suite for serverless functions with automatic build, deployment, and measurements.**

[![CircleCI](https://circleci.com/gh/spcl/serverless-benchmarks.svg?style=shield)](https://circleci.com/gh/spcl/serverless-benchmarks)
![Release](https://img.shields.io/github/v/release/spcl/serverless-benchmarks)
![License](https://img.shields.io/github/license/spcl/serverless-benchmarks)
![GitHub issues](https://img.shields.io/github/issues/spcl/serverless-benchmarks)
![GitHub pull requests](https://img.shields.io/github/issues-pr/spcl/serverless-benchmarks)

SeBS is a diverse suite of FaaS benchmarks that allows an automatic performance analysis of
commercial and open-source serverless platforms. We provide a suite of
[benchmark applications](#benchmark-applications) and [experiments](#experiments),
and use them to test and evaluate different components of FaaS systems.
See the [installation instructions](#installation) to learn how to configure SeBS to use selected
cloud services and [usage instructions](#usage) to automatically launch experiments in the cloud!

SeBS provides support for automatic deployment and invocation of benchmarks on
commercial and black-box platforms
[AWS Lambda](https://aws.amazon.com/lambda/),
[Azure Functions](https://azure.microsoft.com/en-us/services/functions/),
and [Google Cloud Functions](https://cloud.google.com/functions).
Furthermore, we support the open-source platform [OpenWhisk](https://openwhisk.apache.org/)
and offer a custom, Docker-based local evaluation platform.
See the [documentation on cloud providers](docs/platforms.md)
for details on configuring each platform in SeBS.
The documentation describes in detail [the design and implementation of our
tool](docs/design.md), and see the [modularity](docs/modularity.md)
section to learn how SeBS can be extended with new platforms, benchmarks, and experiments.
Find out more about our project in [a paper summary](mcopik.github.io/projects/sebs/).

Do you have further questions not answered by our documentation?
Did you encounter troubles with installing and using SeBS?
Or do you want to use SeBS in your work and you need new features?
Feel free to reach us through GitHub issues or by writing to <marcin.copik@inf.ethz.ch>.

### Paper

When using SeBS, please cite our [Middleware '21 paper](https://dl.acm.org/doi/abs/10.1145/3464298.3476133).
An extended version of our paper is [available on arXiv](https://arxiv.org/abs/2012.14132), and you can
find more details about research work [in this paper summary](https://mcopik.github.io/projects/sebs/).
You can cite our software repository as well, using the citation button on the right.

```
@inproceedings{copik2021sebs,
  author = {Copik, Marcin and Kwasniewski, Grzegorz and Besta, Maciej and Podstawski, Michal and Hoefler, Torsten},
  title = {SeBS: A Serverless Benchmark Suite for Function-as-a-Service Computing},
  year = {2021},
  isbn = {9781450385343},
  publisher = {Association for Computing Machinery},
  address = {New York, NY, USA},
  url = {https://doi.org/10.1145/3464298.3476133},
  doi = {10.1145/3464298.3476133},
  booktitle = {Proceedings of the 22nd International Middleware Conference},
  pages = {64–78},
  numpages = {15},
  keywords = {benchmark, serverless, FaaS, function-as-a-service},
  location = {Qu\'{e}bec city, Canada},
  series = {Middleware '21}
}
```

## Benchmark Applications

For details on benchmark selection and their characterization, please refer to [our paper](#paper).

| Type 		   | Benchmark           | Languages          | Description          |
| :---         | :---:               | :---:              | :---:                |
| Webapps      | 110.dynamic-html    | Python, Node.js    | Generate dynamic HTML from a template. |
| Webapps      | 120.uploader    | Python, Node.js    | Uploader file from provided URL to cloud storage. |
| Multimedia      | 210.thumbnailer    | Python, Node.js    | Generate a thumbnail of an image. |
| Multimedia      | 220.video-processing    | Python    | Add a watermark and generate gif of a video file. |
| Utilities      | 311.compression    | Python   | Create a .zip file for a group of files in storage and return to user to download. |
| Utilities      | 504.dna-visualization    | Python   | Creates a visualization data for DNA sequence. |
| Inference      | 411.image-recognition    | Python    | Image recognition with ResNet and pytorch. |
| Scientific      | 501.graph-pagerank    | Python    | PageRank implementation with igraph. |
| Scientific      | 501.graph-mst    | Python    | Minimum spanning tree (MST)  implementation with igraph. |
| Scientific      | 501.graph-bfs    | Python    | Breadth-first search (BFS) implementation with igraph. |

## Installation

Requirements:
- Docker (at least 19)
- Python 3.6+ with:
    - pip
    - venv
- `libcurl` and its headers must be available on your system to install `pycurl`
- Standard Linux tools and `zip` installed

... and that should be all.

To install the benchmarks with a support for all platforms, use:

```
./install.py --aws --azure --gcp --local
```

It will create a virtual environment in `python-virtualenv`, install necessary Python
dependecies and third-party dependencies. To use SeBS, you must first active the new Python
virtual environment:

```
. python-virtualenv/bin/activate
```

Now you can deploy serverless experiments :-)

The installation of additional platforms is controlled with the `--platform` and `--no-platform`
switches. Currently, the default behavior for `install.py` is to install only the local
environment.

**Make sure** that your Docker daemon is running and your user has sufficient permissions to use it. Otherwise you might see a lot of "Connection refused" and "Permission denied" errors when using SeBS.

To verify the correctness of installation, you can use [our regression testing](#regression).

## Usage

SeBS has three basic commands: `benchmark`, `experiment`, and `local`.
For each command you can pass `--verbose` flag to increase the verbosity of the output.
By default, all scripts will create a cache in directory `cache` to store code with
dependencies and information on allocated cloud resources.
Benchmarks will be rebuilt after a change in source code is detected.
To enforce redeployment of code and benchmark input please use flags `--update-code`
and `--update-storage`, respectively.
**Note:** the cache does not support updating cloud region. If you want to deploy benchmarks
to a new cloud region, then use a new cache directory.

### Benchmark

This command is used to build, deploy, and execute serverless benchmark in cloud.
The example below invokes the benchmark `110.dynamic-html` on AWS via the standard HTTP trigger.

```
./sebs.py benchmark invoke 110.dynamic-html test --config config/example.json --deployment aws --verbose
```

To configure your benchmark, change settings in the config file or use command-line options.
The full list is available by running `./sebs.py benchmark invoke --help`.

### Regression

Additionally, we provide a regression option to execute all benchmarks on a given platform.
The example below demonstrates how to run the regression suite with `test` input size on AWS.

```
./sebs.py benchmark regression test --config config/example.json --deployment aws
```

The regression can be executed on a single benchmark as well:

```
./sebs.py benchmark regression test --config config/example.json --deployment aws --benchmark-name 120.uploader
```

### Experiment

This command is used to execute benchmarks described in the paper. The example below runs the experiment **perf-cost**:

```
./sebs.py experiment invoke perf-cost --config config/example.json --deployment aws
```

The configuration specifies that benchmark **110.dynamic-html** is executed 50 times, with 50 concurrent invocations, and both cold and warm invocations are recorded. 

```json
"perf-cost": {
    "benchmark": "110.dynamic-html",
    "experiments": ["cold", "warm"],
    "input-size": "test",
    "repetitions": 50,
    "concurrent-invocations": 50,
    "memory-sizes": [128, 256]
}
```

To download cloud metrics and process the invocations into a .csv file with data, run the process construct

```
./sebs.py experiment process perf-cost --config example.json --deployment aws
```

### Local

In addition to the cloud deployment, we provide an opportunity to launch benchmarks locally with the help of [minio](https://min.io/) storage.
This allows us to conduct debugging and a local characterization of the benchmarks.

To launch Docker containers, use the following command - this example launches benchmark `110.dynamic-html` with size `test`:

```
./sebs.py local start 110.dynamic-html test out.json --config config/example.json --deployments 1
```

The output file `out.json` will contain the information on containers deployed and the endpoints that can be used to invoke functions:

```
{
  "functions": [
    {
      "benchmark": "110.dynamic-html",
      "hash": "5ff0657337d17b0cf6156f712f697610",
      "instance_id": "e4797ae01c52ac54bfc22aece1e413130806165eea58c544b2a15c740ec7d75f",
      "name": "110.dynamic-html-python-128",
      "port": 9000,
      "triggers": [],
      "url": "172.17.0.3:9000"
    }
  ],
  "inputs": [
    {
      "random_len": 10,
      "username": "testname"
    }
  ]
}
```

In our example, we can use `curl` to invoke the function with provided input:

```
curl 172.17.0.3:9000 --request POST --data '{"random_len": 10,"username": "testname"}' --header 'Content-Type: application/json'
```

To stop containers, you can use the following command:

```
./sebs.py local stop out.json
```

The stopped containers won't be automatically removed unless the option `--remove-containers` has been passed to the `start` command.

## Experiments

For details on experiments and methodology, please refer to [our paper](#paper).

#### Performance & cost

Invokes given benchmark a selected number of times, measuring the time and cost of invocations.
Supports `cold` and `warm` invocations with a selected number of concurrent invocations.
In addition, to accurately measure the overheads of Azure Function Apps, we offer `burst` and `sequential` invocation type that doesn't distinguish
between cold and warm startups.

#### Network ping-pong

Measures the distribution of network latency between benchmark driver and function instance.

#### Invocation overhead

The experiment performs the clock drift synchronization protocol to accurately measure the startup time of a function by comparing
benchmark driver and function timestamps.

#### Eviction model

Executes test functions multiple times, with varying size, memory and runtime configurations, to test for how long function instances stay alive.
The result helps to estimate the analytical models describing cold startups.
Currently supported only on AWS.

## Authors

* [Marcin Copik (ETH Zurich)](https://github.com/mcopik/) - main author.
* [Michał Podstawski (Future Processing SA)](https://github.com/micpod/) - contributed graph and DNA benchmarks, and worked on Google Cloud support.
* [Nico Graf (ETH Zurich)](https://github.com/ncograf/) - contributed implementation of regression tests, bugfixes, and helped with testing and documentation.
* [Kacper Janda](https://github.com/Kacpro), [Mateusz Knapik](https://github.com/maknapik), [JmmCz](https://github.com/JmmCz), AGH University of Science and Technology - contributed together Google Cloud support.
* [Grzegorz Kwaśniewski (ETH Zurich)](https://github.com/gkwasniewski) - worked on the modeling experiments.
* [Paweł Żuk (University of Warsaw)](https://github.com/pmzuk) - contributed OpenWhisk support.

