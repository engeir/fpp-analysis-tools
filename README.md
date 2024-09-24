# fpp-analysis-tools

Collection of tools designed to analyse time series of intermittent fluctuations.

## Installation

The package ~~is published to [PyPI] and~~ can be installed with

```sh
pip install git+https://github.com/uit-cosmo/fpp-analysis-tools
```

If you want to contribute to the project you must first clone the repo to your local
machine, then install the project using [poetry]:

```sh
git clone git@github.com:uit-cosmo/fpp-analysis-tools.git
cd fpp-analysis-tools
poetry install
```

If you plan to use the GPUs, specifically useful for the deconvolution, (local)
installation using either [pixi] or [conda] is supported (the conda environment file is
exported by pixi as `pixi project export conda-environment environment.yml`):

```sh
git clone git@github.com:uit-cosmo/fpp-analysis-tools.git
cd fpp-analysis-tools
# pixi
pixi install
# conda
conda env create --name name-of-my-env --file environment.yml
```

### Troubleshooting

There is a chance you face a `Failed to import CuPy.` issue, or that the libfile is not
found (see a more thorough walk-through
[here](https://www.positioniseverything.net/importerror-libcublas.so.9.0-cannot-open-shared-object-file-no-such-file-or-directory/)).

Check if you can find the file `libcublas.so.10` (or `libcuda.so` or similar) in
`/usr/lib/` or any of its subdirectories. (For example
`find /usr/lib/ -name 'libcublas.so*'`, or with [fd] `fd libcublas.so /usr/lib`). On the
machine used by our group, the following extra step is necessary after installing the
project:

```sh
export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu/"
```

## Usage

You can import all functions directly from `fppanalysis`, such as

```python
import fppanalysis as fa

bin_centers, hist = fa.get_hist(Data, N)
```

[conda]: https://docs.conda.io/en/latest/index.html
[fd]: https://github.com/sharkdp/fd
[poetry]: https://python-poetry.org/
[pixi]: https://pixi.sh/latest/
[pypi]: https://pypi.org/
