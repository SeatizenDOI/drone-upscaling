# Drone Upscaling



### Installation de GDAl 

 Pour installer gdal 


 pip install gdal==[version]

 la version doit matcher avec la version de libgdal

 6. **Troubleshooting:** If `ImportError: /home/bioeos/miniconda3/envs/drone_upscaling_env/bin/../lib/libstdc++.so.6: version 'GLIBCXX_3.4.30' not found (required by /lib/x86_64-linux-gnu/libgdal.so.34)`

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