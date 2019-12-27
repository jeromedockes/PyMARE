"""Core classes and functions."""

from functools import partial

import numpy as np
import pandas as pd

from .estimators import (WeightedLeastSquares, DerSimonianLaird,
                         LikelihoodBased, StanMetaRegression)
from .stats import ensure_2d


class Dataset:
    """Container for input data and arguments to estimators.

    Args:
        estimates (array-like): 1d array of study-level estimates with length K
        variances (array-like, optional): 1d array of study-level variances
            with length K. If not passed, `weights` argument must be set.
        predictors (array-like, optional): 1d or 2d array containing
            study-level predictors (or covariates); has dimensions K x P
        weights (str or array-like, optional): either a string indicating how
            weights should be computed, or a 1d array of study-level weights
             with length K. Valid string values are:
                * "inverse-variance" (default): compute weights as 1/variances
                * "uniform": assign equal weight (1) to all observations
        names ([str], optional): List of length P containing the names of the
            predictors
        add_intercept (bool, optional): If True, an intercept column is
            automatically added to the predictor matrix. If False, the
            predictors matrix is passed as-is to estimators.
        kwargs (dict, optional): Keyword arguments to pass onto estimators
    """
    def __init__(self, estimates, variances=None, predictors=None,
                 weights='inverse-variance', names=None, add_intercept=True,
                 **kwargs):
        self.estimates = ensure_2d(estimates)
        self.variances = ensure_2d(variances)
        self.kwargs = kwargs
        self.weights = self._get_weights(weights)
        X, n = self._get_predictors(predictors, names, add_intercept)
        self.predictors = X
        self.names = n

    def __getattr__(self, key):
        # Provide convenient access to stored kwargs.
        if key in self.kwargs:
            return self.kwargs[key]
        raise AttributeError

    def _get_weights(self, weights):
        if isinstance(weights, 'str'):
            if weights == 'inverse-variance':
                if self.variances is None:
                    raise ValueError("Inverse-variance weighting specified, "
                                     "but no variances were provided!")
                return 1./self.variances
            elif weights == 'uniform':
                return np.ones_like(self.estimates)
            else:
                raise ValueError("'{}' is not a recognized specification for "
                                 "weight computation. Either pass an array of "
                                 "weights, or use 'inverse-variance' or "
                                 "'uniform'.".format(weights))
        else:
            return weights

    def _get_predictors(self, X, names, add_intercept):
        if X is None and not add_intercept:
            raise ValueError("No fixed predictors found. If no X matrix is "
                             "provided, add_intercept must be True!")
        X = pd.DataFrame(X)
        if names is not None:
            X.columns = names
        if add_intercept:
            intercept = pd.DataFrame({'intercept': np.ones(len(self.y))})
            X = pd.concat([intercept, X], axis=1)
        return X.values, X.columns.tolist()

    @property
    def y(self):
        """Alias for the `estimates` attribute."""
        return self.estimates

    @property
    def v(self):
        """Alias for the `variances` attribute."""
        return self.variances

    @property
    def X(self):
        """Alias for the `predictors` attribute."""
        return self.predictors

    @property
    def w(self):
        """Alias for the `weights` attribute."""
        return self.weights


def meta_regression(estimates, variances=None, predictors=None, weights=None,
                    names=None, add_intercept=True, method='ML',
                    ci_method='QP', alpha=0.05, **kwargs):
    """Fits the standard meta-regression/meta-analysis model to provided data.

    Args:
        estimates (array-like): 1d array of study-level estimates with length K
        variances (array-like, optional): 1d array of study-level variances
            with length K. If not passed, `weights` argument must be set.
        predictors (array-like, optional): 1d or 2d array containing
            study-level predictors (or covariates); has dimensions K x P. If
            omitted, add_intercept must be True.
        weights (str or array-like, optional): either a string indicating how
            weights should be computed, or a 1d array of study-level weights
             with length K. Valid string values are:
                * "inverse-variance" (default): compute weights as 1/variances
                * "uniform": assign equal weight (1) to all observations
        names ([str], optional): List of length P containing the names of the
            predictors
        add_intercept (bool, optional): If True, an intercept column is
            automatically added to the predictor matrix. If False, the
            predictors matrix is passed as-is to estimators.
        method (str, optional): Name of estimation method. Defaults to 'ML'.
            Supported estimators include:
                * 'ML': Maximum-likelihood estimator
                * 'REML': Restricted maximum-likelihood estimator
                * 'DL': DerSimonian-Laird estimator
                * 'WLS' or 'FE': Weighted least squares (fixed effects only)
                * 'Stan': Full Bayesian MCMC estimation via Stan
        ci_method (str, optional): Estimation method to use when computing
            uncertainty estimates. Currently only 'QP' is supported. Defaults
            to 'QP'. Ignored if method == 'Stan'.
        alpha (float, optional): Desired alpha level (CIs will have 1 - alpha
            coverage). Defaults to 0.05.
        kwargs: Optional keyword arguments to pass onto the chosen estimator.

    Returns:
        A MetaRegressionResults or BayesianMetaRegressionResults instance,
        depending on the specified method ('Stan' will return the latter; all
        other methods return the former).
    """
    dataset = Dataset(estimates, variances, predictors, weights, names,
                      add_intercept)

    method = method.lower()

    estimator_cls = {
        'ml': partial(LikelihoodBased, method=method),
        'reml': partial(LikelihoodBased, method=method),
        'dl': DerSimonianLaird,
        'wls': WeightedLeastSquares,
        'fe': WeightedLeastSquares,
        'stan': StanMetaRegression,
    }[method]

    # Get estimates
    est = estimator_cls(**kwargs)
    results = est.fit(dataset)
    if hasattr(results, 'compute_stats'):
        results.compute_stats(ci_method=ci_method, alpha=alpha)
    return results
