"""
This module is used by buildout by applying the z3c.recipe.runscript recipe when 
building the RNASeq pipeline parts:

    [shortRNA001C]
    recipe = z3c.recipe.runscript
    update-script = prepare.py:main
    install-script = prepare.py:main
    accession = shortRNA001C
    pipeline = female

Both the update-script and install-script point to the prepare.py module and its "main" method.

The accession attribute is necessary so that the corresponding files and metadata for the 
pipeline run can be found in the accession database.

The pipeline attribute specifies the section defining the pipeline options.
"""

import os
from pprint import pprint
import shutil
from subprocess import call
from RestrictedPython import compile_restricted
from RestrictedPython.Guards import safe_builtins
from RestrictedPython.Guards import full_write_guard
from RestrictedPython.PrintCollector import PrintCollector

def run_python(code, accession):
    """
    Run some restricted Python code for constructing the labels of accessions
    """
    
    if code.startswith("python:"):
        # The python code should be stripped
        raise AttributeError

    # In order to get the result of the Python code out, we have to wrap it like this
    code = 'print ' + code + ';result = printed'
    
    # We compile the code in a restricted environment
    compiled = compile_restricted(code, '<string>', 'exec')
    
    # The getter is needed so that attributes from the accession can be used for the labels
    def mygetitem(obj, attr):
        return obj[attr]
    
    # The following globals are usable from the restricted Python code
    restricted_globals = dict(__builtins__ = safe_builtins, # Use only some safe Python builtins
                              accession = accession,        # The accession is needed for the labels
                              _print_ = PrintCollector,     # Pass this to get hold of the result
                              _getitem_ = mygetitem,        # Needed for accessing the accession
                              _getattr_ = getattr)          # Pass the standard getattr

    # The code is now executed in the restricted environment
    exec(compiled) in restricted_globals
    
    # We collect the result variable from the restricted environment
    return restricted_globals['result']

def install_bin_folder(options, buildout, bin_folder):
    # Always start with a fresh installation, so remove the old bin folder in var/pipeline
    shutil.rmtree(bin_folder, ignore_errors=True)
    # The original code comes from the SVN
    pipeline_bin_folder = os.path.join(buildout['buildout']['directory'], 'src/pipeline/bin')
    # The bin folder is populated from the SVN version of the bin folder
    shutil.copytree(pipeline_bin_folder, bin_folder)
    # The bin folder of the current part should point to the global bin folder
    target = os.path.join(options['location'], 'bin')
    if os.path.exists(target):
        os.remove(target)
    # Make a symbolic link to the global bin folder in var/pipeline in the part
    os.symlink(bin_folder, target)
    # Use the same shebang for all perl scripts
    for perlscript in os.listdir(bin_folder):
        if perlscript.endswith('.pl'):
            file = open(os.path.join(bin_folder, perlscript), 'r')
            # Just the read the first line, which is expected to be the shebang
            shebang = file.readline()
            # Make sure the shebang is as expected
            if not shebang.strip() in ['#!/soft/bin/perl', '#!/usr/bin/perl']:
                print "All perl scripts are expeted to start with #!/soft/bin/perl or #!/usr/bin/perl"
                print "This one (%s) starts with %s" % (perlscript, shebang)
                raise AttributeError
            # Read the rest of the file only, omitting the shebang
            content = file.read()
            file.close()
            # Open the file again, this time for writing
            file = open(os.path.join(bin_folder, perlscript), 'w')
            # Write the new shebang using our own perl version as defined in the buildout.cfg
            file.write("#!%s\n" % buildout['settings']['perl'])
            # Write the rest of the content
            file.write(content)
            file.close()

def install_lib_folder(options, buildout, bin_folder):
    # The lib folder is copied to var/pipeline
    lib_folder = os.path.join(os.path.join(buildout['buildout']['directory'], 'var/pipeline/lib'))
    # Remove the old lib folder in var/pipeline
    shutil.rmtree(lib_folder, ignore_errors=True)
    # The original lib folder is taken from the SVN
    pipeline_lib_folder = os.path.join(buildout['buildout']['directory'], 'src/pipeline/lib')
    # Copy the lin folder over to var/pipeline
    shutil.copytree(pipeline_lib_folder, lib_folder)
    # Make a symbolic link in the part to the lib folder in var/pipeline
    target = os.path.join(options['location'], 'lib')
    # Remove the old link
    if os.path.exists(target):
        os.remove(target)
    # And put in the new link
    os.symlink(lib_folder, target)

def install_results_folder(options, buildout, results_folder):
    # Create a results folder for the results of a pipeline run
    if os.path.exists(results_folder):
        pass
    else:
        os.mkdir(results_folder)
    target = os.path.join(options['location'], 'results')
    # Remove the old link
    if os.path.exists(target):
        os.remove(target)
    # And put in the new link
    os.symlink(results_folder, target)

def install_read_folder(options, buidout, accession):
    # The URL is recognized if it starts like this:
    url_start = 'http://hgdownload-test.cse.ucsc.edu/goldenPath/hg19/encodeDCC/'
    # This is the local path we map to
    path_start = '/users/rg/projects/encode/scaling_up/whole_genome/encode_DCC_mirror/'
    # Create the read folder in the parts folder
    read_folder = os.path.join(options['location'], 'readData')    
    # There are only soft links in this folder, so the whole folder is deleted every time.
    shutil.rmtree(read_folder, ignore_errors=True)
    # Now create the read folder
    os.mkdir(read_folder)
    number_of_reads = len(accession['file_location'].split('\n'))
    for number in range(0, number_of_reads):
        # Get the file location from the accession
        file_location = accession['file_location'].split('\n')[number].strip()
        # Try to recognize the url
        if file_location.startswith(url_start):
            # Remove the url part and try to make a proper file system path
            file_location = os.path.join(path_start, file_location.replace(url_start, ''))
        elif file_location.startswith("http://"):
            # Unrecognized
            raise AttributeError
        # Only accept a path if it is inside of the path we expect.
        # This is so that tricks like ../ don't work
        if not os.path.exists(file_location):
            print "Warning! File does not exist: %s" % file_location 
        # Make symbolic links to the read files
        # Take just the file name from the file location
        filename = os.path.split(file_location)[1]
        # Combine the read folder with the filename to get the target
        target = os.path.join(read_folder, filename)
        os.symlink(file_location, target)

def install_dependencies(options, buildout, bin_folder):

    # Remove any existing flux.sh in the pipeline bin folder
    flux_sh = os.path.join(buildout['buildout']['directory'], 'var/pipeline/bin/flux.sh')
    if os.path.exists(flux_sh):
        os.remove(flux_sh)
    if os.path.exists(flux_sh):
        raise AttributeError
        
    # Use the Java binary as defined in the buildout.cfg
    java = os.path.join(buildout['buildout']['directory'], buildout['settings']['java'])
    # The flux.sh gets install inside the var/pipeline/bin folder
    pipeline_bin = os.path.join(buildout['buildout']['directory'], 'src/flux/bin')
    # The jar file location is defined in the buildout.cfg
    flux_jar = buildout['settings']['flux_jar'] 
    # This is the command used to create the flux.sh shell script
    command = '%s -DwrapperDir="%s" -jar "%s" --install' %(java, pipeline_bin, flux_jar)
    print command
    # Now we can creat the flux.sh file.
    retcode = call(command, shell=True) 
    os.symlink(os.path.join(pipeline_bin, 'flux.sh'), flux_sh)
    if not os.path.exists(flux_sh):
        raise AttributeError
        
     # Make symbolic links to the overlap and flux tools
    target = os.path.join(bin_folder, 'overlap')
    os.symlink(buildout['settings']['overlap'], target)
    if not os.path.exists(target):
        raise AttributeError, "Can't find the overlap binary %s" % buildout['settings']['overlap']

    # Make symbolic links to the gem binaries
    for gem_binary in ['gem-2-sam', 
                       'gem-do-index',
                       'gem-mappability',
                       'gem-mapper',
                       'gem-retriever',
                       'gem-split-mapper']:
        source = os.path.join(buildout['settings']['gem_folder'], gem_binary)
        target = os.path.join(bin_folder, gem_binary)
        os.symlink(source, target)
        if not os.path.exists(target):
            raise AttributeError


def install_pipeline_scripts(options, buildout, accession):
    # The default pipeline section is called "pipeline"
    # If the accession has a pipeline attribute, this overrides the default section name
    pipeline = options.get('pipeline', 'pipeline')

    command = "#!/bin/bash\n"
    command += "bin/start_RNAseq_pipeline.3.0.pl"
    command += " -species '%s'" % accession['species']
    command += " -genome %s" % buildout[pipeline]['GENOMESEQ']
    command += " -annotation %s" % buildout[pipeline]['ANNOTATION']
    command += " -project %s" % buildout[pipeline]['PROJECTID']
    command += " -experiment %s" % options['experiment_id']
    command += " -template %s" % buildout[pipeline]['TEMPLATE']
    # readType = 2x50 
    # readType = 75D 
    # Extract the read length taking the value after the x
    read_length = accession['readType']
    if 'x' in read_length:
        read_length = read_length.split('x')[1]
    if 'D' in read_length:
        read_length = read_length.split('D')[0]
    if read_length.isdigit():
        # read_length needs to be a number, otherwise don't pass it on
        command += " -readlength %s" % read_length
    command += " -cellline '%s'" % accession['cell']
    command += " -rnafrac %s" % accession['rnaExtract']
    command += " -compartment %s" % accession['localization']
    if accession.has_key('replicate'):
        command += " -bioreplicate %s" % accession['replicate']
    command += " -threads %s" % buildout[pipeline]['THREADS']
    command += " -qualities %s" % accession['qualities']
    command += " -cluster %s" % buildout[pipeline]['CLUSTER']
    command += " -database %s" % buildout[pipeline]['DB']
    command += " -commondb %s" % buildout[pipeline]['COMMONDB']
    if buildout[pipeline].has_key('HOST'):
        command += " -host %s" % buildout[pipeline]['HOST']
    command += " -mapper %s" % buildout[pipeline]['MAPPER']
    command += " -mismatches %s" % buildout[pipeline]['MISMATCHES']
    if options.has_key('description'):
        command += " -run_description '%s'" % options['description']
    if buildout[pipeline].has_key('PREPROCESS'):
       command += " -preprocess '%s'" % buildout[pipeline]['PREPROCESS']
    if buildout[pipeline].has_key('PREPROCESS_TRIM_LENGTH'):
       command += " -preprocess_trim_length %s" % buildout[pipeline]['PREPROCESS_TRIM_LENGTH']
    target  = os.path.join(options['location'], 'start.sh')
    f = open(target, 'w')
    f.write(command)
    f.close()
    os.chmod(target,0755)

    target  = os.path.join(options['location'], 'clean.sh')
    command += " -clean"
    f = open(target, 'w')
    f.write(command)
    f.close()
    os.chmod(target,0755)

    command = "#!/bin/bash\n"
    command += "bin/execute_RNAseq_pipeline3.0.pl all |tee -a pipeline.log"
    target  = os.path.join(options['location'], 'execute.sh')
    f = open(target, 'w')
    f.write(command)
    f.close()
    os.chmod(target,0755)

def install_read_list(options, buildout, accession):
    # Add a read.list.txt
    target  = os.path.join(options['location'], 'read.list.txt')
    f = open(target, 'w')
    number_of_reads = len(accession['file_location'].split('\n'))
    for number in range(0, number_of_reads):
        file_location = accession['file_location'].split('\n')[number]
        if accession.has_key('pair_id'):
            pair_id = accession['pair_id'].split('\n')[number]
        else:
            pair_id = buildout['labeling']['pair_id'].strip()
            if pair_id.startswith("python:"):
                pair_id = run_python(pair_id[7:], accession)
        
        if accession.has_key('mate_id'):
            mate_id = accession['mate_id'].split('\n')[number]
        else:
            mate_id = buildout['labeling']['mate_id'].strip()
            if mate_id.startswith("python:"):
                # The mate id gets a postfix of ".1" and ".2"
                mate_id = run_python(mate_id[7:], accession).strip()
                if number_of_reads > 1:
                    if accession.has_key('file_type'):
                        # If file type is given (FASTQRD1, FASTQRD2), use this number
                        mate_id = "%s.%s" % (mate_id,
                                             accession['file_type'].split('\n')[number][-1])
                    else:
                        # In the absence of the file type, just number in order
                        mate_id = "%s.%s" % (mate_id, number+1)
                        
        if accession.has_key('label'):
            label = accession['label'].split('\n')[number]
        else:
            label = buildout['labeling']['label'].strip()
            if label.startswith("python:"):
                label = run_python(label[7:], accession)

        file_name = os.path.split(file_location.strip())[1]
        if file_name.split('.')[-1] == "gz":
            file_name = file_name[:-3]
        labels = (file_name.strip(), 
                  pair_id.strip().replace(' ', ''), 
                  mate_id.strip().replace(' ', ''), 
                  label.strip().replace(' ', ''))
        f.write('\t'.join(labels))
        f.write('\n')
    f.close()


def main(options, buildout):
    """
    This method is called for each part and does the following:

    * Create a fresh readData folder with pointers to the original read files
    
    * bin folder
    
        * The /src/pipeline/bin folder is copied to var/pipeline/bin

        * The shebangs of all Perl scripts in var/pipeline/bin is changed to use 
          the Perl version defined in buildout.cfg

        * Create a fresh link in the part to the var/pipeline/bin folder

    * lib folder

        * The /src/pipeline/lib folder is copied to var/pipeline/lib
    
        * Create a fresh link in the part to the var/pipeline/lib folder

    
        * 
      
    """
    # Without an accession, the part can not be created, because no read files can be linked to
    try:
        accession = buildout[options['accession']]
    except:
        print "Accession not found", options['accession']
        return


    for key, value in accession.items():
        if not key in ['pair_id', 'mate_id', 'label', 'file_location', 'file_type']:
            if '\n' in accession[key]:
                # Collapse the redundant values to make labeling easier
                accession[key] = accession[key].split('\n')[0]

    # The part name is also the experiment id. As it is not given in the options, we need to 
    # extract it from the current location. Sigh.
    options['experiment_id'] = os.path.split(options['location'])[-1]

    bin_folder  = os.path.join(buildout['buildout']['directory'], 'var/pipeline/bin')
    # The bin folder is made available globally to all pipelines in var/pipeline
    # The shebang of all contained scripts has to be changed to use the Perl version 
    # defined in buildout.cfg
    install_bin_folder(options, buildout, bin_folder)

    install_lib_folder(options, buildout, bin_folder)

    results_folder  = os.path.join(buildout['buildout']['directory'], 'var/%s' % options['experiment_id'])
    install_results_folder(options, buildout, results_folder)
    
    # Now check the availability of the files.
    # If the file location is given as a URL, first try to see whether the file can be
    # found locally.
    # If the file is found locally, update the file_location with the local one.
    # If the file is not found locally, print a warning.
    # TODO It would be great to optionally download the file.
    install_read_folder(options, buildout, accession)

    # Install the flux, overlap and gem binaries
    install_dependencies(options, buildout, bin_folder)

    # Install the start, execute and clean shell scripts
    install_pipeline_scripts(options, buildout, accession)

    # Install the read list file defining the labels of the reads
    install_read_list(options, buildout, accession)



