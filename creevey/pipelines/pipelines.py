"""Pipeline class definitions"""
from collections import defaultdict
import logging
from pathlib import Path
import time
from typing import Any, Callable, DefaultDict, Iterable, Optional, Tuple, Union

from joblib import delayed, Parallel
from numpy import iterable
import pandas as pd
from tqdm import tqdm

from creevey.constants import PathOrStr


class Pipeline:
    """
    Class for defining file processing pipelines.

    Attributes
    ----------
    load_func
        Callable that takes a string or `Path` object as single
        positional argument, reads from the corresponding location, and
        returns some representation of its contents.
    ops
        Iterable of callables each of which takes a single positional
        argument. The first element of `ops` must accept the output of
        `load_func`, and each subsequent element must accept the output
        of the immediately preceding element. It is recommended that
        every element of `ops` take and return one common data structure
        (e.g. NumPy arrays for image data) so that those elements can
        be recombined easily.
    check_existing_func
        Callable that takes an output path and checks whether a file
        exists at that path.
    write_func
        Callable that takes the output of the last element of `ops` (or
        the output of `load_func` if `ops` is `None` or empty) and a
        string or `Path` object and writes the former to the location
        specified by the latter.
    run_report_
    """

    def __init__(
        self,
        load_func: Callable[[PathOrStr], Any],
        write_func: Callable[[Any, PathOrStr], None],
        ops: Optional[
            Union[Callable[[Any], Any], Iterable[Callable[[Any], Any]]]
        ] = None,
        check_existing_func: Optional[Callable[[Any], bool]] = (
            lambda x: Path(x).exists()
        ),
    ) -> None:
        self.load_func = load_func
        if callable(ops):
            self.ops = [ops]
        elif iterable(ops):
            self.ops = ops
        elif ops is None:
            self.ops = []
        else:
            raise TypeError('ops must be callable, an iterable of callables, or `None`')
        self._run_report_ = None
        self.write_func = write_func
        self.check_existing_func = check_existing_func

    @property
    def run_report_(self):
        """
        Pandas DataFrame of information about the most recent run.

        Stores input path in the index, output path as "outpath", 0/1
        indicating whether processing was skipped because a file already
        existed at the output path as "skipped_existing", whether
        processing failed due to a handled exception as
        "exception_handled", and a timestamp indicating when processing
        completed as "time_finished".

        Raises
        ------
        AttributeError
            If no run report is available because pipeline has not been
            run.
        """
        if self._run_report_ is None:
            raise AttributeError(
                'Pipeline has not been run, so there is no run report.'
            )
        return self._run_report_

    def __call__(
        self,
        inpaths: Iterable[PathOrStr],
        path_func: Callable[[PathOrStr], PathOrStr],
        n_jobs: int,
        skip_existing: bool = True,
        exceptions_to_catch: Optional[Union[Exception, Tuple[Exception]]] = None,
    ) -> pd.DataFrame:
        """
        Run the pipeline.

        Across `n_jobs` threads, for each path in `inpaths`, if
        `skip_existing` is `True` and `path_func` of that path exists,
        do not do anything. Otherwise, use `load_func` to get the
        resource from that path, pipe its output through `ops`, and
        write out the result with `write_func`.

        Parameters
        ----------
        inpaths
            Iterable of string or Path objects pointing to resources to
            be processed and written out.
        path_func
            Function that takes each input path and returns the desired
            corresponding output path.
        n_jobs
            Number of threads to use.
        skip_existing
            Boolean indicating whether to skip items that would result
            in overwriting an existing file or to overwrite any such
            files.
        exceptions_to_catch
            Tuple of exception types to catch. An exception of one of
            these types will be logged with logging level ERROR and the
            relevant file will be skipped.

        Raises
        ------
        CreeveyProcessingError
            If any unhandled errors arise during file processing

        Notes
        -----
        Logs a warning when `skip_existing` is `True`.

        Stores a run report in `self.run_report_`
        """
        if skip_existing:
            logging.warning(
                'Skipping files where a file exists at the output '
                'location. Pass `skip_existing=False` to overwrite '
                'existing files instead.'
            )

        log_dict = defaultdict(dict)

        try:
            Parallel(n_jobs=n_jobs, prefer='threads')(
                delayed(self._pipeline_func)(
                    path, path_func, skip_existing, log_dict, exceptions_to_catch
                )
                for path in tqdm(inpaths)
            )
        except Exception as e:
            raise CreeveyProcessingError from e
        finally:
            self._run_report_ = pd.DataFrame.from_dict(log_dict, orient='index')

    def run(self, *args, **kwargs):
        """
        Alias for `self.__call__`

        Provided for compatibility with code written before
        `self.__call__` was added.
        """
        return self(*args, **kwargs)

    def _pipeline_func(
        self,
        inpath: PathOrStr,
        outpath_func: PathOrStr,
        skip_existing: bool,
        log_dict: DefaultDict[str, dict],
        exceptions_to_catch: Optional[Union[Tuple, Tuple[Exception]]] = None,
    ) -> None:
        """
        Process one file

        Use `self.load_func` to load the file at `inpath` into memory,
        pipe the result through the functions in `self.ops`, and use
        `self.write_func` to write it to `outpath_func(inpath)`.

        If `skip_existing` is `True`, check up front whether
        `outpath_func(inpath)` exists. If it does, skip the file.

        Catch `exceptions_to_catch` if they arise during file
        processing.

        Parameters
        ----------
        inpath
            Input path
        outpath_func
            Function that takes input path and returns output path
        skip_existing
            Whether or not to skip processing if output path is occupied
        log_dict
            Dictionary of logs
        exceptions_to_catch
            Exception types to catch

        Note
        ----
        Records results in a dict within `log_dict[inpath]` with the
        following attributes

        outpath
            output path
        skipped_existing
            0/1 indicating whether existing file was skipped
        exception_handled
            0/1 indicating whether exception of a type specified in
            `exceptions_to_catch` was handled during processing
        time_finished
            Timestamp indicating when processing finished
        """
        outpath = outpath_func(inpath)
        skipped_existing = False
        exception_handled = False

        if skip_existing and Path(outpath).is_file():
            skipped_existing = True
            logging.debug(
                f'Skipping {inpath} because there is already a file at corresponding '
                f'output path {outpath}'
            )
        else:
            if exceptions_to_catch is None:
                self._run_pipeline_func(inpath, outpath, log_dict=log_dict)
            else:
                try:
                    self._run_pipeline_func(inpath, outpath, log_dict=log_dict)
                except exceptions_to_catch as e:
                    exception_handled = True
                    logging.error(e, inpath)

        inpath_logs = log_dict[inpath]
        inpath_logs['outpath'] = outpath
        inpath_logs['skipped_existing'] = int(skipped_existing)
        inpath_logs['exception_handled'] = int(exception_handled)
        inpath_logs['time_finished'] = time.time()

    def _run_pipeline_func(self, inpath, outpath, **kwargs):
        # `kwargs` included to handle unused `log_dict` so that
        # `_pipeline_func` does not have to change in
        # `CustomReportingPipeline`
        stage = self.load_func(inpath)
        for op in self.ops:
            stage = op(stage)
        self.write_func(stage, outpath)


class CustomReportingPipeline(Pipeline):
    """
    Class for defining file processing pipelines with custom run
    recording.

    Differences from Pipeline parent class:

        `load_func`, each element of `ops`, and `write_func` must each
        accept the string or `Path` object indicating the input item's
        location as an additional positional argument.

        Each element of `ops` and `write_func` must each accept a
        `defaultdict(dict)` object as an additional positional argument.
        Functions defined in Creevey call this item `log_dict`.

    Inside those functions, adding items to `log_dict[inpath]` causes
    them to be added to the "run record" DataFrame that the pipeline
    returns. See Creevey's README for further explanation.
    """

    def _run_pipeline_func(self, inpath, outpath, log_dict):
        stage = self.load_func(inpath, log_dict=log_dict)
        for op in self.ops:
            stage = op(stage, inpath=inpath, log_dict=log_dict)
        self.write_func(stage, outpath, inpath=inpath, log_dict=log_dict)


class CreeveyProcessingError(Exception):
    """Raised when unhandled exception arises during file processing"""

    pass
