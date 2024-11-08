# Use an official Python runtime as a parent image
FROM python:3.12.7-slim

# Add local directory and change permission.
ADD --chown=seatizen . /home/seatizen/app/

# Setup workdir in directory.
WORKDIR /home/seatizen/app

# Install lib.
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgal-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir \
    rasterio==1.4.2 \
    geopandas==1.0.1 \
    gdal==3.8.4 \
    vector3d==1.1.1 

# Change with our user.
USER seatizen