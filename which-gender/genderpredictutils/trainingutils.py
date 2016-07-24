# -*- coding: utf-8 -*-
"""
Miscellaneous helper functions used during training the various models.

@author: Nirmalya Ghosh (and others, see credits)
"""

import gc
import gzip
import time
from collections import defaultdict
from operator import itemgetter

import numpy as np
from sklearn.cross_validation import cross_val_score
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.grid_search import RandomizedSearchCV
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC, SVC
from tabulate import tabulate


def compare_classifiers(clfs, X, y, n_jobs=7, print_scores=True):
    ts = time.time()
    scores = []
    for clf_id, clf in clfs:
        cv_score = get_cv_score(clf_id, clf, X, y, n_jobs=n_jobs)
        scores.append((clf_id, cv_score))
        del clf
        num_unreachable_objects = gc.collect()

    scores = retain_unique(scores, 0)
    scores = sorted(scores, key=lambda (_, x): -x)
    if print_scores==True:
        print(tabulate(scores, floatfmt=".4f", headers=("Model", "F1-score")))
        num_unreachable_objects = gc.collect()
        print_elapsed_time(ts)
    return scores


def find_best_hyperparameters(clf, vectorizer, X, y, param_dist, num_iters=20):
    # Run the grid search
    print("Finding best hyperparameters for {}".format(clf.__class__.__name__))
    random_search = RandomizedSearchCV(clf, param_distributions=param_dist,
                                       n_iter=num_iters, n_jobs=7)
    # random_search.fit(vectorizer.fit_transform(X), y)
    random_search.fit(X, y)

    # Iterate through the scores and print the best 3
    top_scores = sorted(random_search.grid_scores_, key=itemgetter(1),
                        reverse=True)[:3]
    for i, score in enumerate(top_scores):
        print("Model with rank: {0}".format(i + 1))
        print("\tMean validation score: {0:.3f} (std: {1:.3f})".format(
            score.mean_validation_score,
            np.std(score.cv_validation_scores)))
        print("\tParameters: {0}".format(score.parameters))

    return random_search.best_estimator_


def get_cv_score(est_id, est, X, y, n_jobs=1):
    cv_score = cross_val_score(est, X, y, cv=5, n_jobs=n_jobs,
                               scoring="f1").mean()
    # print("Trained: {}\t\tF1-score: {:.4f}, ".format(est_id, cv_score)),
    return cv_score


def get_cv_scores(estimators, X, y, n_jobs=1):
    cv_scores = []
    for est_id, est in estimators:
        cv_score = get_cv_score(est_id, est, X, y, n_jobs=n_jobs)
        cv_scores.append((est_id, cv_score))
    return cv_scores


def print_elapsed_time(ts=None):
    if ts:
        print "\nTime Taken :", "%.1f" % ((time.time() - ts)/60), "minutes\n"
    else:
        print "\nElapsed Time :", "%.1f" % ((time.time() - t0)/60), \
            "minutes to reach this point (from the start)"


def read_GloVe_file(filepath):
    print "Reading", filepath
    glove_w2v = {}
    with gzip.open(filepath, "rb") as lines:
        for line in lines:
            parts = line.split()
            glove_w2v[parts[0]] = np.array(map(float, parts[1:]))
    print("{} keys. First 8 : {}\n".format(len(glove_w2v.keys()),
                                           glove_w2v.keys()[:8]))
    return glove_w2v


def retain_unique(list_of_tuples, tuple_elem_index=0):
    seen = set()
    return [item for item in list_of_tuples if
            item[tuple_elem_index] not in seen and
            not seen.add(item[tuple_elem_index])]


class MeanEmbeddingVectorizer(object):
    # Word vector equivalent of CountVectorizer
    # Each word in each blog post is mapped to its vector;
    # then this helper class computes the mean of those vectors
    # Credit : https://github.com/nadbordrozd/blog_stuff/blob/master/classification_w2v/benchmarking.ipynb
    def __init__(self, word2vec):
        self.word2vec = word2vec
        self.dim = len(word2vec.itervalues().next())
    
    def fit(self, X, y):
        return self 

    def transform(self, X):
        return np.array([
            np.mean([self.word2vec[w] for w in words if w in self.word2vec] 
                    or [np.zeros(self.dim)], axis=0)
            for words in X
        ])


class TfidfEmbeddingVectorizer(object):
    # Word vector equivalent of TfidfVectorizer
    # Credit : https://github.com/nadbordrozd/blog_stuff/blob/master/classification_w2v/benchmarking.ipynb
    def __init__(self, word2vec):
        self.word2vec = word2vec
        self.word2weight = None
        self.dim = len(word2vec.itervalues().next())

    def fit(self, X, y):
        tfidf = TfidfVectorizer(analyzer=lambda x: x)
        tfidf.fit(X)
        # if a word was never seen - it must be at least as infrequent
        # as any of the known words - so the default idf is the max of
        # known idf's
        max_idf = max(tfidf.idf_)
        self.word2weight = defaultdict(
            lambda: max_idf,
            [(w, tfidf.idf_[i]) for w, i in tfidf.vocabulary_.items()])

        return self

    def transform(self, X):
        return np.array([
                            np.mean([self.word2vec[w] * self.word2weight[w]
                                     for w in words if w in self.word2vec] or
                                    [np.zeros(self.dim)], axis=0)
                            for words in X
                            ])
