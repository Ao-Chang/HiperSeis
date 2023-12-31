#! /usr/bin/env python
"""
Add GPS clock time correction csv_data into inventory file to get a modified station xml file

CreationDate:
    24/02/2020

Developer:
    fei.zhang@ga.gov.au

"""

import os
import sys
import io
import pandas as pd

from obspy import read_inventory
from obspy.core import UTCDateTime
from obspy.core.util import AttribDict


def get_csv_correction_data(path_csvfile):
    """
    Read in the csv data from an input file, get the network_code, station_code, csv_data. Format::

        $ head 7D.DE43_clock_correction.csv
        net,sta,date,clock_correction
        7D,DE43,2012-11-27,1.0398489013215846
        7D,DE43,2012-11-28,0.9408504322549281
        7D,DE43,2012-11-29,0.8418519631882714
        7D,DE43,2012-11-30,0.7428534941216148
        7D,DE43,2012-12-01,0.6438550250549583

    :param path_csvfile: input csv file in /g/data/ha3/Passive/SHARED_DATA/GPS_Clock/corrections/
    :return: (network_code, station_code, csv_data)
    """

    with open(path_csvfile, "r") as csvfid:
        all_csv = csvfid.read()

    line2 = all_csv.split('\n')[1]
    # print(line2)

    my_items = line2.split(",")

    network_code = my_items[0].strip()  # network_code = "7D"
    station_code = my_items[1].strip()  # station_code = "DE43"

    return (network_code, station_code, all_csv)


def get_metadata_by_date_range(csv_data, net, sta, start_dt, end_dt):
    """
    Select the csv rows according  net, sta, start_dt, end_dt

    Args:
        csv_data: a string of CSV
        start_dt: obspy.core.utcdatetime.UTCDateTime
        end_dt:  obspy.core.utcdatetime.UTCDateTime

    Returns: a subset of csv in pandas df, selected according to (net, sta, start_dt, end_dt)
    """
    pdf = pd.read_csv(io.StringIO(csv_data))
    # pdf.insert(4,"utcdate", UTCDateTime(0))
    # print(pdf.head())
    pdf["utcdate"] = pdf.apply(lambda row: UTCDateTime(row.date), axis=1)

    _crit = (pdf['net'] == net) & (pdf['sta'] == sta) & (
        pdf['utcdate'] > start_dt) & (pdf['utcdate'] < end_dt)
    pdf2 = pdf.loc[_crit].copy()  # use copy() to fix "SettingWithCopyWarning"

    # drop the columns inplace pdf2 itself will be changed, otherwise will return a new df
    pdf2.drop(['utcdate'], axis=1, inplace=True)
    print("The shapes = ", pdf.shape, pdf2.shape)

    # print(pdf2.head())

    # return pdf2.to_csv(index=False)
    return pdf2


def add_gpscorrection_into_stationxml(csv_file, input_xml, out_dir=None, mformat="CSV"):
    """
    Read in the correction CSV data from a file, get the station metadata node from input_xml file,
    then add the CSV data into the station xml node to write into out_xml

    :param csv_file: input csv file with correction data
    :param input_xml: input original stationXML file which contains the metadata for the network and station of csv_file
    :param out_xml:  Directory of the output xml file
    :return: full path of the output xml file
    """

    GA_NameSpace = "https://github.com/GeoscienceAustralia/hiperseis"

    (net, sta, csv_data) = get_csv_correction_data(csv_file)

    # path2_myxml = "/home/feizhang/Githubz/hiperseis/tests/testdata/7D_2012_2013.xml"
    my_inv = read_inventory(input_xml, format='STATIONXML')

    # https://docs.obspy.org/packages/autogen/obspy.core.inventory.inventory.Inventory.select.html#obspy.core.inventory.inventory.Inventory.select

    selected_inv = my_inv.select(network=net, station=sta)

    # print(selected_inv)

    station_list = selected_inv.networks[0].stations

    # redefine the selected_inv
    for a_station in station_list:  # loop over all Stations

        # get station star end date and split csv_data
        start_dt = a_station.start_date
        end_dt = a_station.end_date
        mpdf = get_metadata_by_date_range(
            csv_data, net, sta, start_dt, end_dt)

        #print("Station %s= %s %s" %(a_station, start_dt,end_dt))

        my_tag = AttribDict()
        my_tag.namespace = GA_NameSpace
        if mformat == "CSV":
            my_tag.value = mpdf.to_csv(index=False)
        elif mformat == "JSON":
            my_tag.value = mpdf.to_json(orient="records", date_format="epoch",
                                        force_ascii=True, date_unit="ms", default_handler=None, indent=2)
        else:
            print("The format %s is not supported" % mformat)

        a_station.extra = AttribDict()
        a_station.extra.GAMetadata = my_tag

    # prepare to write out a modified xml file

    mod_stationxml_with_extra = '%s.%s_station_metadata_%s.xml' % (net, sta,mformat)

    if out_dir is not None and os.path.isdir(out_dir):
        mod_stationxml_with_extra = os.path.join(
            out_dir, mod_stationxml_with_extra)

    selected_inv.write(mod_stationxml_with_extra, format='STATIONXML',
                       nsmap={'GeoscienceAustralia': GA_NameSpace})

    # my_inv.write('modified_inventory.xml', format='STATIONXML')

    return mod_stationxml_with_extra


def extract_csvdata(path2xml):
    """
    Read the station xml file and extract the csv data to be parsed by pandas

    :param path2xml: path_to_stationxml
    :return: csv_str
    """

    mcount = 0
    new_inv = read_inventory(path2xml, format='STATIONXML')

    for i in range(len(new_inv.networks[0].stations)):
        csv_str = new_inv.networks[0].stations[i].extra.GAMetadata.value
        # print(csv_str)
        # print(type(csv_str))

        pdf = pd.read_csv(io.StringIO(csv_str))

        print(pdf.shape)
        mcount = mcount + pdf.shape[0]

    return mcount


# ----------------------------------------------------------------------------------------------------------------
# Quick test code
# Example How to run:
# python add_time_corrections.py  /g/data/ha3/Passive/SHARED_DATA/GPS_Clock/corrections/7D.CZ40_clock_correction.csv
#                                ../../tests/testdata/7D_2012_2013.xml      ~/tmpdir/
# python add_time_corrections.py ./OA.CF28_clock_correction.csv /g/data/ha3/Passive/_AusArray/OA/ASDF_cleaned/OA_stations_2017-2018.xml
# ----------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":

    USAGE = "python %s gps_clock_corr_csv sta_inventory_xml [out_dir]" % sys.argv[0]

    if len(sys.argv) < 3:
        print(USAGE)
        sys.exit(1)
    else:
        time_correction_csvfile = sys.argv[1]
        my_inventory = sys.argv[2]

    if len(sys.argv) >= 4:
        out_dir = sys.argv[3]
    else:
        out_dir = None

    output_xml = add_gpscorrection_into_stationxml(
        time_correction_csvfile, my_inventory, out_dir=out_dir)
        #time_correction_csvfile, my_inventory, out_dir=out_dir, mformat="JSON")

    print("A new inventory file is created:", output_xml)

    # Optional test to extract the extra meta_data and make a pandas dataframe for future use.
    # mcount = extract_csvdata(output_xml)
    # print("Number of CSV rows", mcount)
