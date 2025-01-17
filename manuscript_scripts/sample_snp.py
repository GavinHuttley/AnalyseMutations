"""sampling SNP data from Ensembl"""
import os, sys, cPickle, gzip

import click

from cogent import DNA
from cogent.core.moltype import IUPAC_DNA_complements
from cogent.util.option_parsing import parse_command_line_parameters
from cogent.db.ensembl import Species, HostAccount, Genome
from cogent.db.ensembl.region import Variation

from phyg import util, path

__author__ = "Yicheng Zhu, Gavin Huttley"
__copyright__ = "Copyright 2015, Gavin Huttley"
__credits__ = ["Yicheng Zhu", "Gavin Huttley"]
__license__ = "GPL"
__maintainer__ = "Gavin Huttley"
__email__ = "Gavin.Huttley@anu.edu.au"
__status__ = "Development"


_nucs = set(DNA)

def is_valid(snp, verbose=False):
    """True if validation status is not None, freqs exist for 2 nucleotide alleles"""
    if snp.Validation is None or snp.AlleleFreqs is None:
        return False
    
    alleles = snp.AlleleFreqs.getDistinctValues('allele')
    
    freqs = [1 for v in snp.AlleleFreqs.getRawData('freq') if type(v) == float]
    
    if verbose:
        print alleles
        print "freqs",freqs
        print  len(alleles) != 2 or sum(freqs) == 0 or alleles - _nucs
        print  len(alleles), sum(freqs), alleles - _nucs
    
    # set diff will be empty if alleles are just nucleotides
    if len(alleles) != 2 or sum(freqs) == 0 or alleles - _nucs:
        return False
    
    return True

def get_max_allele_freqs(freq_table):
    """returns max freq for each allele from pops where polymorphic"""
    freq_table = freq_table.filtered(lambda x: type(x) == float and 0 < x < 1,
                                columns='freq')
    alleles_freqs = dict((a, []) for a in freq_table.getDistinctValues('allele'))
    pops = freq_table.getDistinctValues('population_id')
    for pop in pops:
        pop_freqs = freq_table.filtered(lambda x: x == pop, columns='population_id')
        assert pop_freqs.Shape[0] != 1, pop_freqs
        
        data = pop_freqs.getRawData(['allele', 'freq'])
        
        for allele, freq in data:
            alleles_freqs[allele].append(freq)
    
    return [(a, max(alleles_freqs[a])) for a in alleles_freqs]

def get_snp_dump_data(snp, genic=False):
    """returns all SNP data for dumping."""
    allele_freqs = get_max_allele_freqs(snp.AlleleFreqs)
    alleles = snp.Alleles
    ancestral = snp.Ancestral
    flank_5prime = snp.FlankingSeq[0]
    flank_3prime = snp.FlankingSeq[1]
    if genic:
        gene = list(snp.getFeatures('gene'))[0]
        pep_alleles = str(snp.PeptideAlleles)
        gene_loc = str(gene.Location)
        gene_id = gene.StableId
    else:
        pep_alleles = gene_loc = gene_id = 'None'
    
    record = [snp.Symbol, str(snp.Location), str(snp.Location.Strand),
            snp.Effect, str(allele_freqs), alleles, str(ancestral),
            str(flank_5prime), str(flank_3prime), pep_alleles, gene_id, gene_loc]
    
    return record

def get_basic_snp_dump_data(snp, genic=False):
    """returns basic SNP data for dumping."""
    allele_freqs = get_max_allele_freqs(snp.AlleleFreqs)
    alleles = snp.Alleles
    ancestral = snp.Ancestral
    if genic:
        features = list(snp.getFeatures('gene'))
        if not features:
            msg = '\n'.join(["#" * 20, str(snp), "#" * 20, ''])
            sys.stderr.write(msg)
            return None
        
        gene = features[0]
        gene_loc = str(gene.Location)
        gene_id = gene.StableId
    else:
        gene_loc = gene_id = 'None'
    
    if type(snp.Effect) not in (str, unicode):
        effect = ','.join(snp.Effect)
    else:
        effect = snp.Effect
    record = [snp.Symbol, str(snp.Location), str(snp.Location.Strand),
            effect, str(allele_freqs), alleles, str(ancestral), gene_id, gene_loc]
    
    return record

def read_snp_records(genome, pickled, effect):
    effect = unicode(effect)
    if effect.startswith('exon'):
        effect = set(['missense_variant', 'synonymous_variant'])
    else:
        effect = set([effect])
    
    infile = {'gz': gzip.open}.get(pickled.split('.')[-1], open)(pickled)
    while True:
        try:
            record = cPickle.load(infile)
            if not effect & record['consequence_types']:
                continue
            
            snp = Variation(genome, genome.CoreDb, Effect=None,
                            Symbol=record['variation_name'], data=record)
            yield snp
        except EOFError:
            break
    infile.close()
    

@click.command()
@click.option('-r', '--release', default=None, help='Ensembl release.')
@click.option('-o', '--output', default=None, type=click.Path(resolve_path=True), help='Path to write files.')
@click.option('-s', '--snp_records', default=None, type=click.Path(resolve_path=True),
    help='Path to pickled SNP data dump from Ensembl.')
@click.option('-c', '--snp_effect', default=None,
    type=click.Choice(['missense_variant', 'synonymous_variant', 'intron_variant',
             'exon_variant', 'intergenic_variant']),
        help='SNP effect.')
@click.option('-l','--limit', default=None, type=int,
        help='Number of results to return.')
@click.option('-F', '--force_overwrite', is_flag=True, help='Overwrite existing files.')
@click.option('-D', '--dry_run', is_flag=True, help='Do a dry run of the analysis without writing output.')
@click.option('--verbose', is_flag=True, help='Verbose output.')
def main(release, output, snp_records, snp_effect, limit, force_overwrite, dry_run, verbose):
    output_filename = os.path.join(output, '%s_%s.txt.gz' % (snp_effect,
                    release))
    
    if os.path.exists(output_filename) and not force_overwrite:
        print "File exists, exiting.."
    
    genic = not snp_effect.startswith('intergenic')
    
    path.create_path(output)
    
    print 'Will write to %s' % output_filename
    
    account = HostAccount(*os.environ['ENSEMBL_ACCOUNT'].split())
    human = Genome('human', Release=release, account=account)
    
    reader = read_snp_records(human, snp_records, snp_effect)
    
    outfile = util.open_(output_filename, 'w')
    chroms = '12345678910111213141516171819202122XY'
    
    for num, snp in enumerate(reader):
        if num % 100 == 0:
            print 'Snp number %d' % num
            outfile.flush()
        
        try:
            location = snp.Location.CoordName
        except AssertionError, msg:
            print
            print '#' * 20
            print snp.Symbol, msg.message
            print '#' * 20 
            print
            continue
        
        if location not in chroms or not is_valid(snp, verbose):
            if verbose:
                print "NOT VALID"
                print snp
                print snp.AlleleFreqs
            
            continue
        
        validation = snp.Validation
        if type(validation) != str:
            validation = ','.join(validation)
        
        record = get_basic_snp_dump_data(snp, genic=genic)
        if record is None:
            continue
        
        num += 1
        outfile.write('\t'.join(record) + '\n')
    
    print "num written", num
    outfile.close()

if __name__ == "__main__":
    main()