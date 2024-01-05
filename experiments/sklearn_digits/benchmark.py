from itertools import permutations
import random

import numpy as np
from sklearn import datasets
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import torch
import torch.nn.functional as F
import torch.nn as nn
from torch.utils.data import Dataset

from auto_mi.base import MetadataBase
from auto_mi.tasks import Task, Example, TRAIN, MI
from auto_mi.utils import DirModelWriter, TarModelWriter
from auto_mi.mi import FreezableClassifier
from auto_mi.cli import train_cli


TRAIN_RATIO = 0.7
NUM_DIGITS = 3


# TODO: commonise with other sklearn tasks
class PermutedDigitsTask(Task):
    def __init__(self, seed=0., train=True, **kwargs):
        super().__init__(seed=seed, train=train)
        p = list(permutations(range(NUM_DIGITS)))
        # Shuffle the permutations so we see examples where all output classes
        # are remapped.
        r = random.Random(seed)
        r.shuffle(p)
        self._permutations = p

    def get_dataset(self, i, type=TRAIN, **_) -> Dataset:
        """
        Gets the dataset for the ith example of this task.
        """
        return PermutedDigitsExample(self._permutations[i % len(self._permutations)], type=type)

    @property
    def input_shape(self):
        return (8, 8,)

    @property
    def output_shape(self):
        return (NUM_DIGITS, )

    @property
    def mi_output_shape(self):
        return (NUM_DIGITS, NUM_DIGITS)

    def criterion(self, x, y):
        return F.nll_loss(x, y)


class PermutedDigitsExample(Example):
    def __init__(self, permutation_map, type=TRAIN):
        self._permutation_map = permutation_map

        if type==MI:
            return

        digits_dataset = datasets.load_digits()
        X = digits_dataset.data
        y = digits_dataset.target

        # Filter down to just NUM_DIGITS classes
        example_mask = [_y < NUM_DIGITS for _y in y]
        X = [x for x, t in zip(X, example_mask) if t]
        y = [_y for _y, t in zip(y, example_mask) if t]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        scaler = StandardScaler()
        X_train = scaler.fit_transform(X_train)
        X_test = scaler.transform(X_test)


        if type == TRAIN:
            self.X = X_train
            self.y = y_train
        else:
            self.X = X_test
            self.y = y_test

    def __getitem__(self, i):
        x = self.X[i].astype(np.float32)
        y = self.y[i]
        return x.reshape((8, 8)), self._permutation_map[y]

    def __len__(self):
        return len(self.X)

    def get_metadata(self):
        return {'permutation_map': self._permutation_map}
    
    def get_target(self):
        return F.one_hot(torch.tensor(self._permutation_map)).to(torch.float32)


class DigitsClassifier(nn.Module, MetadataBase):
    def __init__(self, *_):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 20, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(20, 20, kernel_size=3, padding=1)
        self.fc1 = nn.Linear(20 * 2 * 2, 30)
        self.fc2 = nn.Linear(30, 10)

    def forward(self, x):
        x = x.unsqueeze(1)
        x = F.relu(F.max_pool2d(self.conv1(x), 2))
        x = F.relu(F.max_pool2d(self.conv2(x), 2))
        x = x.view(-1, 20 * 2 * 2)
        x = F.relu(self.fc1(x))
        x = self.fc2(x)
        return F.log_softmax(x, dim=1)


class FreezableDigitsClassifier(DigitsClassifier, FreezableClassifier):
    def __init__(self, *_):
        """
        Any two layers, or a single layer, can be frozen without significantly
        effecting the performance. 
        """
        DigitsClassifier.__init__(self)
        FreezableClassifier.__init__(self, __file__)
        self.frozen = (0, 1)


if __name__ == '__main__':
    train_cli(
        DirModelWriter,
        DirModelWriter,
        PermutedDigitsTask,
        # DigitsClassifier,
        FreezableDigitsClassifier,
        default_subject_model_epochs=100,
        default_subject_model_batch_size=1000,
        default_subject_model_lr=0.01,
        default_interpretability_model_num_layers=1,
        default_interpretability_model_num_heads=2,
        default_interpretability_model_positional_encoding_size=2048,
    )