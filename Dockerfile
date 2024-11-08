# Use an official Python runtime as a parent image
FROM ghcr.io/osgeo/gdal:ubuntu-small-latest

# Add local directory and change permission.
ADD --chown=seatizen . /home/seatizen/app/

# Setup workdir in directory.
WORKDIR /home/seatizen/app

# Install lib.
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3-pip build-essential && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir --break-system-package \
    rasterio==1.4.2 \
    geopandas==1.0.1 \
    vector3d==1.1.1 \
    tqdm==4.66.6

# Change with our user.
USER seatizen

# Define the entrypoint script to be executed.
ENTRYPOINT ["python", "main.py"]