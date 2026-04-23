import os

import pytest


@pytest.fixture
def base_url() -> str:
    return os.environ.get("VECTORLESS_BASE_URL", "http://localhost:8080")


@pytest.fixture
def api_key() -> str:
    return os.environ.get("VECTORLESS_API_KEY", "vl_test_sk_1234567890abcdef")


SAMPLE_MARKDOWN = """\
# Introduction to Machine Learning

Machine learning is a subset of artificial intelligence that enables systems to learn from data.

## Supervised Learning

Supervised learning uses labeled training data to learn a mapping function.

### Classification

Classification predicts categorical labels. Common algorithms include:
- Logistic Regression
- Decision Trees
- Support Vector Machines

### Regression

Regression predicts continuous values. Examples:
- Linear Regression
- Polynomial Regression

## Unsupervised Learning

Unsupervised learning finds hidden patterns in unlabeled data.

### Clustering

Clustering groups similar data points together.
- K-Means
- DBSCAN
- Hierarchical Clustering

### Dimensionality Reduction

Techniques like PCA reduce the number of features while preserving information.

## Deep Learning

Deep learning uses neural networks with multiple layers to learn complex representations.

### Convolutional Neural Networks

CNNs are specialized for processing grid-like data such as images.

### Recurrent Neural Networks

RNNs are designed for sequential data like text and time series.
"""
