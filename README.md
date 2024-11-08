<p align="center">
  <a href="https://github.com/SeatizenDOI/drone-upscaling/graphs/contributors"><img src="https://img.shields.io/github/contributors/SeatizenDOI/drone-upscaling" alt="GitHub contributors"></a>
  <a href="https://github.com/SeatizenDOI/drone-upscaling/network/members"><img src="https://img.shields.io/github/forks/SeatizenDOI/drone-upscaling" alt="GitHub forks"></a>
  <a href="https://github.com/SeatizenDOI/drone-upscaling/issues"><img src="https://img.shields.io/github/issues/SeatizenDOI/drone-upscaling" alt="GitHub issues"></a>
  <a href="https://github.com/SeatizenDOI/drone-upscaling/blob/master/LICENSE"><img src="https://img.shields.io/github/license/SeatizenDOI/drone-upscaling" alt="License"></a>
  <a href="https://github.com/SeatizenDOI/drone-upscaling/pulls"><img src="https://img.shields.io/github/issues-pr/SeatizenDOI/drone-upscaling" alt="GitHub pull requests"></a>
  <a href="https://github.com/SeatizenDOI/drone-upscaling/stargazers"><img src="https://img.shields.io/github/stars/SeatizenDOI/drone-upscaling" alt="GitHub stars"></a>
  <a href="https://github.com/SeatizenDOI/drone-upscaling/watchers"><img src="https://img.shields.io/github/watchers/SeatizenDOI/drone-upscaling" alt="GitHub watchers"></a>
</p>
<div align="center">
  <a href="https://github.com/SeatizenDOI/drone-upscaling">View framework</a>
  ·
  <a href="https://github.com/SeatizenDOI/drone-upscaling/issues">Report Bug</a>
  ·
  <a href="https://github.com/SeatizenDOI/drone-upscaling/issues">Request Feature</a>
</div>

<div align="center">

# Drone Upscaling

</div>


## Installation

To ensure a consistent environment for all users, this project uses a Conda environment defined in a `requirements.yml` file. Follow these steps to set up your environment:

1. **Install Conda:** If you do not have Conda installed, download and install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda](https://www.anaconda.com/products/distribution).

2. **Dependencies:** You need to install `sudo apt-get install build-essentials build-essential libgdal-dev`. You need to match the libgdal version with gdal pip package version.

3. **Create the Conda Environment:** Navigate to the root of the project directory and run the following command to create a new environment from the `requirements.yml` file:
   ```bash
   conda env create -f requirements.yml
   ```

4. **Activate the Environment:** Once the environment is created, activate it using:
   ```bash
   conda activate drone_upscaling_env
   ```

 5. **Troubleshooting:** If `ImportError: /home/bioeos/miniconda3/envs/drone_upscaling_env/bin/../lib/libstdc++.so.6: version 'GLIBCXX_3.4.30' not found (required by /lib/x86_64-linux-gnu/libgdal.so.34)`

  Use:

  `sudo find / -name libstdc++.so.6` to find your local file.

  `strings /usr/lib/x86_64-linux-gnu/libstdc++.so.6 | grep GLIBCXX` to check if the `version 'GLIBCXX_3.4.32'` is present.

  Then:
```bash
ln -sf /usr/lib/x86_64-linux-gnu/libstdc++.so.6 /home/bioeos/miniconda3/envs/drone_upscaling_env/lib/libstdc++.so
ln -sf /usr/lib/x86_64-linux-gnu/libstdc++.so.6 /home/bioeos/miniconda3/envs/drone_upscaling_env/lib/libstdc++.so.6
```


### Docker

The goal of this docker image is to be a ready-made environment to easily run scripts.

Build command :

```bash
docker build -f Dockerfile -t drone-upscaling:latest .
```

Run command :
```bash
docker run --user 1000 --rm \
  -v ./config/:/home/seatizen/app/config \
  -v ./data:/home/seatizen/app/data \
 --name drone-upscaling drone-upscaling:latest -c --config_path ./config/config_troudeau.json
```

### Build singularity container

`module load singularity/3.6.4`

`singularity build -f drone_upscaling.sif docker://seatizendoi/drone-upscaling:latest`

### PBS

```bash
#!/bin/bash

#PBS -l select=1:ncpus=32:mem=40g
#PBS -l walltime=2:00:00
#PBS -N drone_upscaling
#PBS -q omp
#PBS -S /bin/bash

signal_handler() {
        pkill --parent "${$}"
}
trap signal_handler EXIT
cd /home1/datahome/villien/PBS/drone_upscaling/

module load singularity/3.6.4


singularity run --pwd /home/seatizen/app/ \
--bind /home1/datahome/villien/PBS/drone_upscaling/config:/home/seatizen/app/config \
--bind /home1/datawork/villien/drone_upscaling_data:/home/seatizen/app/data \
drone_upscaling.sif -c --config_path ./config/config_stleu.json

qstat -f $PBS_JOBID
```