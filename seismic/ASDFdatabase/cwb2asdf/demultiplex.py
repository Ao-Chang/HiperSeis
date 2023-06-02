#!/bin/env python
"""
Description:
    Utility Program for running the demultiplex binary in parallel.
References:

CreationDate:   09/04/19
Developer:      rakib.hassan@ga.gov.au

Revision History:
    LastUpdate:     00/04/19   RH
    LastUpdate:     2020-04-10  Fei Zhang  Take over and clean-up the code.

"""

import glob
import os
import random
import subprocess
from seismic.misc import ProgressTracker
import click
from mpi4py import MPI

def runprocess(cmd, get_results=False):
    results = []
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in p.stdout:
        if (get_results): results.append(line.strip())
        # else: print line
    # end for

    # for line in p.stderr:
    #    print line
    p.wait()

    return p.returncode, results
# end func

def split_list(lst, npartitions):
    k, m = divmod(len(lst), npartitions)
    return [lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(npartitions)]
# end func

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('input-folder', required=True,
                type=click.Path(exists=True))
@click.argument('output-folder', required=True,
                type=click.Path(exists=True))
@click.option('--extension', default='ms',
              help="File extension for miniseed files; default is 'ms'")
@click.option('--restart', is_flag=True, default=False, help='Restart job')
def process(input_folder, output_folder, extension, restart):
    """
    INPUT_FOLDER: Path to input folder containing mseed files to be demultiplexed \n
    OUTPUT_FOLDER: Output folder \n

    Example usage:
    mpirun -np 2 python demultiplex.py ./ /tmp/output

    Note:
    """

    comm = MPI.COMM_WORLD
    nproc = comm.Get_size()
    rank = comm.Get_rank()

    msfiles = None
    if (rank == 0):
        msfiles = glob.glob(input_folder + '/*.%s' % (extension))

        random.Random(nproc).shuffle(msfiles)  # using nproc as seed so that shuffle produces the same
        # ordering when jobs are restarted.

        msfiles = split_list(msfiles, nproc)
    # end if

    msfiles = comm.scatter(msfiles, root=0)

    path = os.path.dirname(os.path.abspath(__file__))

    # Progress tracker
    progTracker = ProgressTracker(output_folder=output_folder, restart_mode=restart)

    for ifn, fn in enumerate(msfiles):
        if (progTracker.increment()):
            pass
        else:
            print(('Found results for mseed file %s. Moving along..' % (fn)))
            continue
        # end if

        cmd = '%s/demultiplex %s %s %s.%s' % (path, fn, output_folder, rank, ifn)

        ec, results = runprocess(cmd, get_results=True)

        print((ec, results))
    # end for


#######################################################################################################
# Example Cmdline run:  mpirun -np 2 python3 demultiplex.py /Datasets/ /tmp/Output_Miniseeds/
#######################################################################################################
if (__name__ == '__main__'):
    process()
