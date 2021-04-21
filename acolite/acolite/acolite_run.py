## def acolite_run
## runs acolite processing for given settings file/dict, new version
## written by Quinten Vanhellemont, RBINS
## 2021-04-01
## modifications: 2021-04-14 (QV) added output to settings if not configured
##                2021-04-15 (QV) test/parse input files

def acolite_run(settings, inputfile=None, output=None, limit=None, verbosity=0):
    import datetime, os, mimetypes
    import acolite as ac

    print('Running generic ACOLITE processing - {}'.format(ac.version))
    ## time of processing start
    time_start = datetime.datetime.now()

    ## get user settings
    ## these are updated with sensor specific settings in acolite_l2r
    setu = ac.acolite.settings.parse(None, settings=settings, merge=False)
    if 'runid' not in setu: setu['runid'] = time_start.strftime('%Y%m%d_%H%M%S')
    if 'output' not in setu:
        if output is None:
            setu['output'] = os.getcwd()
        else:
            setu['output'] = output

    ## log file for l1r generation
    log_file = '{}/acolite_run_{}_log_file.txt'.format(setu['output'],setu['runid'])
    log = ac.acolite.logging.LogTee(log_file)
    print('Run ID - {}'.format(setu['runid']))

    ## earthdata credentials from settings file
    for k in ['EARTHDATA_u', 'EARTHDATA_p']:
        kv = setu[k] if k in setu else ac.config[k]
        if len(kv) == 0: continue
        os.environ[k] = kv

    ## parse inputfile
    if inputfile is not None:
        if type(inputfile) != list:
            if type(inputfile) == str:
                inputfile = inputfile.split(',')
            else:
                inputfile = list(inputfile)
        setu['inputfile'] = inputfile
    nscenes = len(setu['inputfile'])

    ## parse output
    if output is not None: setu['output'] = output

    ## get defaults settings for l1r processing
    setu_l1r = ac.acolite.settings.parse(None, settings=setu, merge=True)

    ## make list of lists to process, one list if merging tiles
    if type(setu_l1r['inputfile']) is not list: setu_l1r['inputfile'] = [setu_l1r['inputfile']]

    ## check if a list of files is given
    tmp_files = setu_l1r['inputfile'] if type(setu_l1r['inputfile']) == list else setu_l1r['inputfile'].split(',')
    inputfile_list = []
    for file in tmp_files:
        print(file)
        if os.path.isdir(file):
            inputfile_list.append(file)
        else:
            mime = mimetypes.guess_type(file)
            if mime[0] != 'text/plain':
                if os.path.exists(file): inputfile_list.append(file) ## assume we can process this file
                continue
            with open(file, 'r') as f:
                for l in f.readlines():
                    l = l.strip()
                    if len(l) == 0: continue
                    cfiles = []
                    for fn in l.split(','):
                        if os.path.exists(fn): cfiles.append(fn)
                    if len(cfiles)>0: inputfile_list.append(cfiles)
    nruns = len(inputfile_list)

    ## track processed scenes
    processed = {}
    ## run through bundles to process
    for ni in range(nruns):
        ## bundle to process
        bundle = inputfile_list[ni]
        processed[ni] = {'input': bundle}

        ## run l1 convert
        ret = ac.acolite.acolite_l1r(bundle, setu_l1r)
        if len(ret) == 0: continue
        l1r_files, l1r_setu = ret
        processed[ni]['l1r'] = l1r_files

        ## do atmospheric correction
        l2r_files, l2t_files = [], []
        l2w_files = []
        for l1r in l1r_files:
            gatts = ac.shared.nc_gatts(l1r)
            if 'acolite_file_type' not in gatts:
                gatts['acolite_file_type'] = 'L1R'

            if gatts['acolite_file_type'] == 'L1R':
                ## run ACOLITE
                ret = ac.acolite.acolite_l2r(l1r, settings = setu, verbosity = verbosity)
                if len(ret) != 2: continue
                l2r, l2r_setu = ret
            else:
                l2r = '{}'.format(l1r)
                l2r_setu = ac.acolite.settings.parse(gatts['sensor'], settings=setu)

            if l2r_setu['l2r_export_geotiff']: ac.output.nc_to_geotiff(l2r)
            l2r_files.append(l2r)

            ## run TACT
            if l2r_setu['tact_run']:
                ret = ac.tact.tact_gem(l1r, output_atmosphere = l2r_setu['tact_output_atmosphere'],
                                            output_intermediate = l2r_setu['tact_output_intermediate'])
                l2t_files.append(ret)
                if l2r_setu['l2r_export_geotiff']: ac.output.nc_to_geotiff(ret)

                ## make l2t maps
                if l2r_setu['tact_map']:
                    ac.acolite.acolite_map(ret, settings=l2r_setu)

            ## make rgb maps
            if l2r_setu['rgb_rhot'] | l2r_setu['rgb_rhos']:
                ac.acolite.acolite_map(l2r, settings = l2r_setu, plot_all=False)

            ## compute l2w parameters
            if l2r_setu['l2w_parameters'] is not None:
                if type(l2r_setu['l2w_parameters']) is not list: l2r_setu['l2w_parameters'] = [l2r_setu['l2w_parameters']]
                ret = ac.acolite.acolite_l2w(l2r, settings=l2r_setu)
                if l2r_setu['l2w_export_geotiff']: ac.output.nc_to_geotiff(ret)
                l2w_files.append(ret)

                ## make l2w maps
                if l2r_setu['map_l2w']:
                    ac.acolite.acolite_map(ret, settings=l2r_setu)

        if len(l2r_files) > 0: processed[ni]['l2r'] = l2r_files
        if len(l2t_files) > 0: processed[ni]['l2t'] = l2t_files
        if len(l2w_files) > 0: processed[ni]['l2w'] = l2w_files
    ## end processing loop
    log.__del__()

    return(processed)