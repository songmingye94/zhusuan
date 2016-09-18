#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
import itertools

import tensorflow as tf
import six
from six.moves import zip, map

from .utils import log_mean_exp
from .evaluation import is_loglikelihood


def advi(model, observed, latent, reduction_indices=1, given=None):
    """
    Implements the automatic differentiation variational inference (ADVI)
    algorithm. For now we assume all latent variables have been transformed in
    the model definition to have their support on R^n.

    :param model: A model object that has a method logprob(latent, observed)
        to compute the log joint likelihood of the model.
    :param observed: A dictionary of (string, Tensor) pairs. Given inputs to
        the observed variables.
    :param latent: A dictionary of (string, (Tensor, Tensor)) pairs. The
        value of two Tensors represents (output, logpdf) given by the
        `zhusuan.layers.get_output` function for distribution layers.
    :param reduction_indices: The sample dimension(s) to reduce when
        computing the variational lower bound.
    :param given: A dictionary of (string, Tensor) pairs. This is used when
        some deterministic transformations have been computed in variational
        posterior and can be reused when evaluating model joint log likelihood.
        This dictionary will be directly passed to the model object.

    :return: A Tensor. The variational lower bound.
    """
    latent_k, latent_v = map(list, zip(*six.iteritems(latent)))
    latent_outputs = dict(zip(latent_k, map(lambda x: x[0], latent_v)))
    latent_logpdfs = map(lambda x: x[1], latent_v)
    given = given if given is not None else {}
    lower_bound = model.log_prob(latent_outputs, observed, given) - \
        sum(latent_logpdfs)
    lower_bound = tf.reduce_mean(lower_bound, reduction_indices)
    return lower_bound


def iwae(model, observed, latent, reduction_indices=1, given=None):
    """
    Implements the importance weighted lower bound from (Burda, 2015).

    :param model: A model object that has a method logprob(latent, observed)
        to compute the log joint likelihood of the model.
    :param observed: A dictionary of (string, Tensor) pairs. Given inputs to
        the observed variables.
    :param latent: A dictionary of (string, (Tensor, Tensor)) pairs. The
        value of two Tensors represents (output, logpdf) given by the
        `zhusuan.layers.get_output` function for distribution layers.
    :param reduction_indices: The sample dimension(s) to reduce when
        computing the variational lower bound.
    :param given: A dictionary of (string, Tensor) pairs. This is used when
        some deterministic transformations have been computed in variational
        posterior and can be reused when evaluating model joint log likelihood.
        This dictionary will be directly passed to the model object.

    :return: A Tensor. The importance weighted lower bound.
    """
    return is_loglikelihood(model, observed, latent, reduction_indices, given)


def rws(model, observed, latent, reduction_indices=1, given=None):
    """
    Implements Reweighted Wake-sleep from (Bornschein, 2015).

    :param model: A model object that has a method logprob(latent, observed)
        to compute the log joint likelihood of the model.
    :param observed: A dictionary of (string, Tensor) pairs. Given inputs to
        the observed variables.
    :param latent: A dictionary of (string, (Tensor, Tensor)) pairs. The
        value of two Tensors represents (output, logpdf) given by the
        `zhusuan.layers.get_output` function for distribution layers.
    :param reduction_indices: The sample dimension(s) to reduce when
        computing the log likelihood.
    :param given: A dictionary of (string, Tensor) pairs. This is used when
        some deterministic transformations have been computed in the proposal
        and can be reused when evaluating model joint log likelihood.
        This dictionary will be directly passed to the model object.

    :return: A 1-D Tensor. The cost to minimize given by Reweighted Wake-sleep.
    :return: A 1-D Tensor of shape (batch_size,). Estimated log likelihoods.
    """
    latent_k, latent_v = map(list, zip(*six.iteritems(latent)))
    latent_outputs = dict(zip(latent_k, map(lambda x: x[0], latent_v)))
    latent_logpdfs = map(lambda x: x[1], latent_v)
    given = given if given is not None else {}
    log_joint = model.log_prob(latent_outputs, observed, given)
    entropy = -sum(latent_logpdfs)
    log_w = log_joint + entropy
    log_w_max = tf.reduce_max(log_w, reduction_indices, keep_dims=True)
    w_u = tf.exp(log_w - log_w_max)
    w_tilde = tf.stop_gradient(w_u / tf.reduce_sum(w_u, reduction_indices,
                                                   keep_dims=True))
    log_likelihood = log_mean_exp(log_w, reduction_indices)
    fake_log_joint_cost = -tf.reduce_sum(w_tilde*log_joint, reduction_indices)
    fake_proposal_cost = tf.reduce_sum(w_tilde*entropy, reduction_indices)
    cost = fake_log_joint_cost + fake_proposal_cost
    return cost, log_likelihood
