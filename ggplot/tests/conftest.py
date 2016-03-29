from __future__ import division
import os
import warnings
import inspect
import shutil
import locale
import functools

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backends import backend_agg, backend_pdf, backend_svg
from matplotlib.testing.compare import compare_images
from matplotlib import cbook
import six

from .. import ggplot

__all__ = ['cleanup']

TOLERANCE = 17

if not os.path.exists(os.path.join(
        os.path.dirname(__file__), 'baseline_images')):
    raise IOError(
        "The baseline image directory does not exist. "
        "This is most likely because the test data is not installed. "
        "You may need to install ggplot from source to get the "
        "test data.")


def ggplot_equals(gg, right):
    """
    Compare ggplot object to image determined by `right`

    Parameters
    ----------
    gg : ggplot
        ggplot object
    right : str | tuple
        Identifier. If a tuple, then first element is the
        identifier and the second element is the tolerance
        for the image comparison.

    This function is meant to monkey patch ggplot.__eq__
    so that tests can use the `assert` statement.
    """
    if isinstance(right, (tuple, list)):
        name, tol = right
    else:
        name, tol = right, TOLERANCE

    fig = gg.draw()
    test_file = inspect.stack()[1][1]
    filenames = make_test_image_filenames(name, test_file)

    # Save the figure before testing whether the original image
    # actually exists. This make creating new tests much easier,
    # as the result image can afterwards just be copied.
    fig.savefig(filenames.result)
    if os.path.exists(filenames.baseline):
        shutil.copyfile(filenames.baseline, filenames.expected)
    else:
        msg = "Baseline image {} is missing"
        raise Exception(msg.format(filenames.baseline))

    err = compare_images(filenames.expected, filenames.result,
                         tol, in_decorator=True)
    gg._err = err  # For the pytest error message
    return False if err else True


ggplot.__eq__ = ggplot_equals


def pytest_assertrepr_compare(op, left, right):
    if (isinstance(left, ggplot) and
            isinstance(right, (six.string_types, tuple)) and
            op == "=="):

        msg = ("images not close: {actual:s} vs. {expected:s} "
               "(RMS {rms:.2f})".format(**left._err))
        return [msg]


def make_test_image_filenames(name, test_file):
    """
    Create filenames for testing

    Parameters
    ----------
    name : str
        An identifier for the specific test. This will make-up
        part of the filenames.
    test_file : str
        Full path of the test file. This will determine the
        directory structure

    Returns
    -------
    out : Bunch
        Object with 3 attributes to store the generated filenames

            - result
            - baseline
            - expected

        `result`, is the filename for the image generated by the test.
        `baseline`, is the filename for the baseline image to which
        the result will be compared.
        `expected`, is the filename to the copy of the baseline that
        will be stored in the same directory as the result image.
        Creating a copy make comparison easier.
    """
    if '.png' not in name:
        name = name + '.png'

    basedir = os.path.abspath(os.path.dirname(test_file))
    basename = os.path.basename(test_file)
    subdir = os.path.splitext(basename)[0]

    baseline_dir = os.path.join(basedir, 'baseline_images', subdir)
    result_dir = os.path.abspath(os.path.join('result_images', subdir))

    if not os.path.exists(result_dir):
        cbook.mkdirs(result_dir)

    base, ext = os.path.splitext(name)
    expected_name = '{}-{}{}'.format(base, 'expected', ext)

    filenames = cbook.Bunch(
        baseline=os.path.join(baseline_dir, name),
        result=os.path.join(result_dir, name),
        expected=os.path.join(result_dir, expected_name))
    return filenames


# This is called from the cleanup decorator
def _setup():
    # The baseline images are created in this locale, so we should use
    # it during all of the tests.
    try:
        locale.setlocale(locale.LC_ALL, str('en_US.UTF-8'))
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, str('English_United States.1252'))
        except locale.Error:
            warnings.warn(
                "Could not set locale to English/United States. "
                "Some date-related tests may fail")

    plt.switch_backend('Agg')  # use Agg backend for these test
    if mpl.get_backend().lower() != "agg":
        msg = ("Using a wrong matplotlib backend ({0}), "
               "which will not produce proper images")
        raise Exception(msg.format(mpl.get_backend()))

    # These settings *must* be hardcoded for running the comparison
    # tests
    mpl.rcdefaults()  # Start with all defaults
    mpl.rcParams['text.hinting'] = True
    mpl.rcParams['text.antialiased'] = True
    # mpl.rcParams['text.hinting_factor'] = 8

    # Clear the font caches.  Otherwise, the hinting mode can travel
    # from one test to another.
    backend_agg.RendererAgg._fontd.clear()
    backend_pdf.RendererPdf.truetype_font_cache.clear()
    backend_svg.RendererSVG.fontd.clear()
    # make sure we don't carry over bad plots from former tests
    msg = ("no of open figs: {} -> find the last test with ' "
           "python tests.py -v' and add a '@cleanup' decorator.")
    assert len(plt.get_fignums()) == 0, msg.format(plt.get_fignums())


def _teardown():
    plt.close('all')
    # reset any warning filters set in tests
    warnings.resetwarnings()


def cleanup(testfunc):
    """
    Decorator to add cleanup to the testing function

      @cleanup
      def test_something():
          " ... "

    Note that `@cleanup` is useful *only* for test functions
    that draw plots.
    """
    @functools.wraps(testfunc)
    def wrapper(*args, **kwargs):
        _setup()
        testfunc(*args, **kwargs)
        _teardown()
    return wrapper