# -*- coding: utf-8 -*-
"""
Created on Tue Mar 15 12:17:30 2022

@author: mcontini
"""
import random
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter
from lib.CameraCalculator import CameraCalculator
from math import radians, atan2, pi, asin, sin, cos, degrees
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
from scipy.interpolate import interp1d, LinearNDInterpolator, NearestNDInterpolator
from scipy.interpolate import griddata
from scipy.spatial import KDTree
from rtree import index

def random_points_within(poly, num_points):
    # Inputs :
    # 1.poly = polygon coordinates
    # 2.num_points = nb of random points to sample in the polygon
    
    # Outputs :
    # 1.points = vector of random points sampled in the polygon
    
    min_x, min_y, max_x, max_y = poly.bounds

    points = []

    while len(points) < num_points:
        random_point = Point([random.uniform(min_x, max_x), random.uniform(min_y, max_y)])
        if (random_point.within(poly)):
            points.append(random_point)

    return points
    
def dest_from_start(lat1, lon1, d, bearing) :
    # Inputs :
    # 1.lat1 = latitude of the starting point in degrees
    # 2.lon1 = longitude of the starting point in degrees
    # 3.d = distance from the starting point in m
    # 4.bearing = direction from one place to another in degrees
    
    # Outputs :
    # 1.lat2 = latitude of the destination point in degrees
    # 2.lon2 = longitude of the destination point in degrees
    
    # we'll do all the computations in KM for a sake of simplicity
    d = d * 1e-3
    R = 6378.137 # Radius of earth in KM
    ang_dist = d/R
    # CAVEAT : we'll do all the computations in radians for a sake of simplicity
    lat1 = radians(lat1)
    lon1 = radians(lon1)
    bearing = radians(bearing)
    
    lat2 = asin( sin(lat1) * cos(ang_dist) + cos(lat1) * sin(ang_dist) * cos(bearing) )
    # Python reverses the arguments of ATAN2 wrt the function "Destination point given distance 
    # and bearing from start point" in :
    # https://www.movable-type.co.uk/scripts/latlong.html
    lon2 = lon1 + atan2(  sin(bearing) * sin(ang_dist) * cos(lat1) , cos(ang_dist) - sin(lat1) * sin(lat2))
    #
    lat2 = degrees(lat2)
    lon2 = degrees(lon2)
    return lat2, lon2
    
def get_dist_and_angle(p, q) :
    # Inputs :
    # 1.p = first cartesian point of the shapely.geometry.Point type
    # 2.q = second cartesian point of the shapely.geometry.Point type

    # Outputs :
    # 1.d = distance between p and q
    # 2.angle = angle between the pq vector and the x-axis in degrees
    
    angle = atan2(q.y - p.y, q.x - p.x) * 180 / pi
    d = ((((q.x - p.x)**2) + ((q.y - p.y)**2) )**0.5)
    
    return d, angle

def footprint_calculator2(df, cfg_prog):
    # Inputs :
    # 1.df = dataframe with lat, lon, yaw, roll, pitch informations
    # 2.cfg_prog = dict with camera informations (field of view) and number of sampling points
    
    # Outputs :
    # 1.The function save a "total_overlap.png" image in the root directory with the 
    # coverage of the mission
    # 2.The function save a "sample_points.png" image in the root directory showing the 
    # random sampled points
    # 3.The function save a "mission_coverage.png" image in the root directory showing the 
    # coverage index over a random grid of points
    # 4.The function returns a vector "overlap_poly" with all the polygons associated to each
    # photo
    
    # interpolate Lat_corr&Lng_corr grid on Depth_corr values in order to get
    # depth values on Lat&Lng grid
    x = np.array(df.Lat_corr)
    y = np.array(df.Lng_corr)
    z = np.array(df.Depth_corr)
    xi = np.array(df.Lat)
    yi = np.array(df.Lng)
    # we have to compute zi_subs with the "nearest" method because the interpolation with "linear" and "cubic"
    # methods return "NaN" values fot points outside the convex hull
    zi_sub = griddata((x,y),z,(xi,yi),method='nearest')
    zi = griddata((x,y),z,(xi,yi),method=cfg_prog['mesh']['method'])
    # subs NaN values in zi with corresponding val in zi_subs
    zi[np.isnan(zi)] = zi_sub[np.isnan(zi)]
    df['Depth_photog'] = zi
    
    #############################################################
    # 1.Plot the total overlap of the mission
    #############################################################  
    
    # define parameters
    fov_x = cfg_prog['photog']['fov_x']
    fov_y = cfg_prog['photog']['fov_y']
    # nb. of sample points from which we'll compute the overlapDPTH index
    sample_points = cfg_prog['photog']['sample_points']
    # output path
    # save current dataframe to local file
    figpath = cfg_prog['path']['destpath']
    # define plot
    plt.figure(1)
    fig, ax = plt.subplots()
    # define vector of overlapping polygons
    overlap_poly = []
    # loop over each photo
    c=CameraCalculator()
    for gps2_index, gps2_row in df.iterrows():
            # get current position of the camera
            lat1 = gps2_row.Lat
            lon1 = gps2_row.Lng
            # get current parameters of the camera
            roll = gps2_row.Roll
            pitch = gps2_row.Pitch
            bearing = gps2_row.Yaw
            depth = gps2_row.Depth_photog
            # compute the bbox for the current photo in a camera system related
            bbox=c.getBoundingPolygon(radians(fov_x), radians(fov_y),
                                      depth, radians(roll),
                                      radians(pitch), radians(bearing))
            # vectors of longitudes and latitudes of the bbox of the current photo
            lat_vec = []
            lon_vec = []
            p1 = Point(0, 0)
            # iterate over the bbox points and compute the bbox in the lonlat system
            for i, p in enumerate(bbox):
                p2 = Point(p.x,  p.y)
                # compute the distance between p and q
                # and the angle between the pq vector and the x-axis in degrees
                d, angle = get_dist_and_angle(p1, p2)
                # compute the distance between the camera position and the current point
                # of the current polygon
                lat2, lon2 = dest_from_start(lat1, lon1, d, angle)
                lat_vec.append(lat2)
                lon_vec.append(lon2)
            # add current polygon to vector of polygons
            overlap_poly.append(Polygon(zip(lon_vec, lat_vec)))
            # plot current polygon
            plt.fill(lon_vec, lat_vec, color='r', zorder=0)

    # plot the whole trip on top of the polygons
    plt.scatter(x=df['Lng'], y=df['Lat'], color='y', marker=".", s=1,linewidths = 1, zorder=1)
    # prevent scientific notation 
    ax.ticklabel_format(useOffset=False)
    # specify format of floats for tick labels
    ax.xaxis.set_major_formatter(FormatStrFormatter('%.4f'))
    # less labels on x axis
    plt.locator_params(nbins=8)
    # define graph labels
    plt.xlabel("Lng")
    plt.ylabel("Lat")
    plt.title("Total overlap")
    file_name = 'total_overlap.png'
    print('\nSaving ', file_name, ' image in path\n', figpath)
    figname = figpath+file_name
    plt.savefig(figname,dpi=600)

    #############################################################
    # 2.Plot the sample points
    #############################################################  
    
    # get Lng and Lat of polygon points
    lat_point_list = df["Lat"]
    lon_point_list = df["Lng"]
    # define polygon of the mission
    poly = Polygon(zip(lon_point_list, lat_point_list))
    poly_lon, poly_lat = poly.exterior.coords.xy
    # extract the convex hull of the polygon
    # i.e. returns a representation of the smallest convex Polygon 
    # containing all the points in the object unless the number of 
    # points in the object is less than three
    hull = poly.convex_hull
    # get lat & lon coordinates of the convex hull
    hull_lon, hull_lat = hull.exterior.coords.xy
    
    points = random_points_within(hull, sample_points)
    # define plot
    plt.figure(2)
    fig, ax = plt.subplots()

    for p in points:
        plt.scatter(p.x, p.y, color='r', linewidths = 0.2, zorder=0)
    # prevent scientific notation 
    ax.ticklabel_format(useOffset=False)
    # specify format of floats for tick labels
    ax.xaxis.set_major_formatter(FormatStrFormatter('%.4f'))
    # less labels on x axis
    plt.locator_params(nbins=8)
    # define graph labels
    plt.xlabel("Lng")
    plt.ylabel("Lat")
    plt.title("Sample points distribution")
    file_name = 'sample_points.png'
    print('\nSaving ', file_name, ' image in path\n', figpath)
    figname = figpath+file_name
    plt.savefig(figname,dpi=600)
    
    #############################################################
    # 3.Plot the overlap index
    #############################################################
    
    # compute the overlap index :
    # define a vector of dimension |Nb_points| and loop
    # over each points and over each photo in order to 
    # see if the point is in the photo polygon

    counts = np.zeros((len(points), 1))

    for idx, curr_point in enumerate(points):
        for curr_poly in overlap_poly :
            if curr_point.within(curr_poly) :
                counts[idx] = counts[idx]+1
    # overlap index
    ov_idx = np.count_nonzero(counts)/counts.size
    
    # define plot
    plt.figure(3)
    fig, ax = plt.subplots()
    # plot
    plt.scatter([p.x for p in points], [p.y for p in points], c=counts, cmap='Reds')
    # prevent scientific notation 
    ax.ticklabel_format(useOffset=False)
    # specify format of floats for tick labels
    ax.xaxis.set_major_formatter(FormatStrFormatter('%.4f'))    
    # less labels on x axis
    plt.locator_params(nbins=8)
    # define graph labels
    plt.xlabel("Lng")
    plt.ylabel("Lat")
    # define title
    title = 'Mission coverage : ', ov_idx
    plt.title(title)    
    # show the legend colormap
    plt.colorbar()
    file_name = 'mission_coverage.png'
    print('\nSaving ', file_name, ' image in path\n', figpath)
    figname = figpath+file_name
    plt.savefig(figname,dpi=600)
    
    return overlap_poly, points, counts

def photog_index(overlap_poly, df, cfg_prog) :
    # Inputs :
    # 1.overlap_poly = vector with all the polygons associated to each photo
    # 2.df = dataframe with lat, lon, yaw, roll, pitch informations 
    # 3.cfg_prog = dict with camera informations (field of view) and number of sampling points

    # Outputs :
    # 1.The function save a "photogrammetry_overlap.png" image in the root directory with the 
    # overlap between each photo and the union of all the other photos
    # 2.The function returns a dataframe "df" to which is added the column "photog_vec" with the 
    # overlap between each photo and the union of all the other photos
   
    
    #############################################################
    # 1.Compute the photogrammetry index
    #############################################################

    figpath = cfg_prog['path']['destpath']
    photog_vec = []
    # create "index" object in order to speedup computations
    # https://rtree.readthedocs.io/en/latest/tutorial.html
    idx = index.Index()
    # add each polygon to the idx object
    for pos, curr_poly in enumerate(overlap_poly):
        idx.insert(pos, curr_poly.bounds)
    # loop over polygons
    for pos, curr_poly in enumerate(overlap_poly):
        # compute indexes of polygons that intersect the current polygon
        intersections_idx = list(idx.intersection(curr_poly.bounds))
        # remove index of the current polygon from the "intersections_idx"
        intersections_idx.remove(pos)
        # merge all the polygons that intersect the current polygon
        merged_poly = unary_union([overlap_poly[pos] for pos in intersections_idx])
        # compute intersection between current polygon and all the others
        intersection_poly = curr_poly.intersection(merged_poly)
        # percent recouvrement
        curr_per = intersection_poly.area/curr_poly.area
        photog_vec.append(curr_per)
    photog_vec = np.array(photog_vec, dtype=np.float32)
    df["photog_vec"] = photog_vec
    #define plot
    plt.figure(1)
    fig, ax = plt.subplots()
    plt.scatter(df.Lng, df.Lat, c=photog_vec,  s=10, cmap='Reds')
    # prevent scientific notation 
    ax.ticklabel_format(useOffset=False)
    # specify format of floats for tick labels
    ax.xaxis.set_major_formatter(FormatStrFormatter('%.4f'))
    # less labels on x axis
    plt.locator_params(nbins=8)
    # define graph labels
    plt.xlabel("Lng")
    plt.ylabel("Lat")
    photog_index = np.mean(df.photog_vec)
    # define title
    title = "Photogrammetry overlap : ", photog_index
    plt.title(title)
    # show the legend colormap
    plt.colorbar()
    file_name = 'photogrammetry_overlap.png'
    print('\nSaving ', file_name, ' image in path\n', figpath)
    figname = figpath+file_name
    plt.savefig(figname,dpi=600)
    # retourner df avec photog_vec
    
    return df
