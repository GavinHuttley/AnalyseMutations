"""export seq files for different mutation types"""
from __future__ import division

import os, sys, time, re
from itertools import permutations
from optparse import make_option
from cogent.util.option_parsing import parse_command_line_parameters

from mutation_motif.util import open_, create_path, abspath, just_nucs, load_from_fasta
from mutation_motif import profile, motif_count

from util import logging, set_logger, get_file_hexdigest

fn_suffixes = re.compile(r"\.(fa|fasta)\.(gz|gzip|bz2)$")

def get_counts_filename(align_path, output_dir):
    """returns counts output path
    
    Arguments:
        - align_path: path to the alignment file. The basename will be modified to use a .txt suffix
        - output_dir: directory where the counts file is to be written
    """
    
    fn = os.path.basename(align_path)
    fn = fn_suffixes.sub(".txt", fn)
    counts_filename = os.path.join(output_dir, fn)
    return counts_filename

def align_to_counts(opts):
    '''returns counts table from alignment of sequences centred on a SNP'''
    
    if len(args) > 1:
        raise RuntimeError("too many positional args")
    
    if not opts.dry_run:
        create_path(opts.output_path)
    
    print "Deriving counts from sequence file"
    direction = tuple(opts.direction.split('to'))
    chosen_base = direction[0]
    orig_seqs = load_from_fasta(os.path.abspath(opts.align_path))
    seqs = orig_seqs.ArraySeqs
    seqs = just_nucs(seqs)
    orig, ctl = profile.get_profiles(seqs, chosen_base=chosen_base, step=1,
                                     flank_size=opts.flank_size, seed=opts.seed)
    
    # convert profiles to a motif count table
    orig_counts = motif_count.profile_to_seq_counts(orig, flank_size=opts.flank_size)
    ctl_counts = motif_count.profile_to_seq_counts(ctl, flank_size=opts.flank_size)
    counts_table = motif_count.get_count_table(orig_counts, ctl_counts, opts.flank_size*2)
    counts_table = counts_table.sorted(columns='mut')
    return counts_table


script_info = {}
script_info['brief_description'] = ""
script_info['script_description'] = "export tab delimited counts table from "\
"alignment centred on SNP position. Output file is written to the same "\
"path with just the file suffix changed from fasta to txt."

script_info['required_options'] = [
     make_option('-a','--align_path', help='fasta aligned file centred on mutated position.'),
     make_option('-o','--output_path', help='Path to write data.'),
     make_option('-f','--flank_size', type=int, help='Number of bases per side to include.'),
     make_option('--direction', default=None,
                 choices=['AtoC', 'AtoG', 'AtoT', 'CtoA', 'CtoG', 'CtoT', 'GtoA', 'GtoC',
                          'GtoT', 'TtoA', 'TtoC', 'TtoG'], help='Mutation direction.'),
    ]

script_info['optional_options'] = [
    make_option('-S', '--seed',
        help='Seed for random number generator (e.g. 17, or 2015-02-13). Defaults to system time.'),
    make_option('-D','--dry_run', action='store_true', default=False,
        help='Do a dry run of the analysis without writing output.'),
    make_option('-r','--reason', help='Reason for running analysis (for Sumatra log).'),
    ]

script_info['version'] = '0.1'
script_info['authors'] = 'Gavin Huttley'

if __name__ == "__main__":
    option_parser, opts, args =\
       parse_command_line_parameters(**script_info)
    
    if not opts.seed:
        opts.seed = str(time.time())
    
    opts.align_path = abspath(opts.align_path)
    opts.output_path = abspath(opts.output_path)
    
    if not opts.dry_run:
        set_logger(os.path.join(opts.output_path, 'run.log'))
        logging.info("command_string: %s" % ' '.join(sys.argv))
        logging.info("vars: %s" % str(vars(opts)))
        
    
    start_time = time.time()
    
    # run the program
    counts_table = align_to_counts(opts)
    counts_filename = get_counts_filename(opts.align_path, opts.output_path)
    if not opts.dry_run:
        counts_table.writeToFile(counts_filename, sep='\t')
        md5sum = get_file_hexdigest(counts_filename)
        logging.info("output file: %s" % counts_filename)
        logging.info("output file md5 sum: %s" % md5sum)
        
    
    
    # determine runtime
    duration = time.time() - start_time
    