"""
Given the chemical maps made from chem_images, perform radial profile calculations
"""
import paths
import pylab as pl
import os
from scipy import ndimage
import itertools
from astropy.io import fits
import radio_beam
import numpy as np
from astropy import units as u
import pyregion
import image_tools
from astropy import wcs
from constants import continuum_frequency
from line_to_image_list import labeldict

import re
import glob

region_names = {'e2': 'e2_exclude_e2w.reg',
                'north': 'd2_core.reg',
               }

continua = {
    # todo?  make a naturally weighted merged continuum image...
    'merge': 'merge/continuum/merge_selfcal_allspw_selfcal_4ampphase_mfs_tclean_deeperbroader.image.pbcor.fits',
    '': 'W51_te_continuum_best.fits',
}

for regfn,region,fignum,imtype,suffix,outsuffix in (
    ('d2_core.reg','north',1,'max','','d2',),
    ('d2_core.reg','north',2,'max','_merge','d2',),
    ('d2_core.reg','north',3,'max','_merge_natural','d2',),
    ('e2_exclude_e2w.reg','e2',1,'m0','',''),
    ('e2_exclude_e2w.reg','e2',2,'m0','_merge',''),
    ('e2_exclude_e2w.reg','e2',3,'m0','_merge_natural',''),
    ('e2_exclude_e2w.reg','e2',1,'max','',''),
    ('e2_exclude_e2w.reg','e2',2,'max','_merge',''),
    ('e2_exclude_e2w.reg','e2',3,'max','_merge_natural',''),
   ):

    reg = pyregion.open(paths.rpath(regfn))

    path_template = paths.dpath("chemslices/chemical_{2}_slabs_{0}_*{1}.fits"
                                .format(region, suffix, imtype))

    files = glob.glob(path_template)

    linestyles = {name: itertools.cycle(['-'] + ['--'] + [':'] + ['-.'])
                  for name in region_names}

    linere = re.compile("chemical_{0}_slabs_[^_]*_(.*?)"
                        "{1}.fits"
                        .format(imtype, suffix))

    # start with continuum
    if 'merge' in suffix:
        contfn = continua['merge']
    else:
        contfn = continua['']
    files = [paths.dpath(contfn)] + files

    for plotspecies in ("CH3OH", "CH3OCHO", "HNCO", "NH2CHO"):
        fig = pl.figure(fignum)
        fig.clf()
        ax = pl.gca()
        #ax.set_title(region+suffix+" "+imtype)
        
        plotted_species = []

        for ii,fn in enumerate(files):
            skip = False
            if 'merge' in fn and 'merge' not in suffix:
                # this is a way to skip _merge when looking for chemname.fits
                skip = True
                continue
            if plotspecies not in fn and ii>0:
                skip = True
                continue
            fh = fits.open(fn)

            linestyle = next(linestyles[region])

            if 'BMAJ' not in fh[0].header:
                print("File {0} does not have BMAJ".format(fn))
                skip = True
                continue
            try:
                beam = radio_beam.Beam.from_fits_header(fh[0].header)
            except KeyError:
                print("File {0} doesn't have beam info in the header".format(fn))
                skip = True
                continue

            assert not skip

            mywcs = wcs.WCS(fh[0].header)
            pixscale = (mywcs.pixel_scale_matrix.diagonal()**2).sum()**0.5
            #ppbeam = (beam.sr/(pixscale**2*u.deg**2)).decompose().value / u.beam
            #print("fn  {0} ppbeam={1:0.2f}".format(fn, ppbeam))

            data = fh[0].data
            mask = reg.get_mask(fh[0]) & np.isfinite(data)

            # crop to fit
            slices = ndimage.find_objects(mask)[0]
            mywcs = mywcs[slices]
            data = data[slices]
            mask = mask[slices]

            center = mywcs.wcs_world2pix(reg[0].coord_list[0], reg[0].coord_list[1], 0)

            nr, bins, rprof = image_tools.radialprofile.azimuthalAverage(data,
                                                                         mask=mask,
                                                                         center=center,
                                                                         binsize=1.0,
                                                                         return_nr=True)

            if ii==0:
                ax.plot(bins*pixscale*3600., rprof * beam.jtok(continuum_frequency),
                        label='Continuum', linestyle='-', alpha=0.25, zorder=-10,
                        linewidth=4, color='k')
            else:
                species = linere.search(fn).groups()[0]
                if species in plotted_species:
                    raise ValueError("Duplicate")
                plotted_species.append(species)
                ax.plot(bins*pixscale*3600., rprof,
                        label=labeldict[species], linestyle=linestyle)
                print(species, end=', ')
        print(".  ", end="")

        if imtype == 'max':
            ax.set_ylabel("Azimuthally Averaged Peak Brightness (K)")
        elif imtype == 'm0':
            ax.set_ylabel("Azimuthally Averaged Flux (K km/s)")
        ax.set_xlabel("Radius (arcsec)")

        #box = ax.get_position()
        #ax.set_position([box.x0, box.y0, box.width * 0.6, box.height])

        # Put a legend to the right of the current axis
        ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))

        print("Completed {0} {1} {2} {3}".format(region, suffix, imtype, plotspecies))
        fig.savefig(paths.fpath("chemslices/radialprofile_{2}_{3}_{0}{4}{1}.png"
                                .format(region, suffix, imtype, plotspecies, outsuffix)),
                    bbox_inches='tight')
        fig.savefig(paths.fpath("chemslices/radialprofile_{2}_{3}_{0}{4}{1}.pdf"
                                .format(region, suffix, imtype, plotspecies, outsuffix)),
                    bbox_inches='tight')
