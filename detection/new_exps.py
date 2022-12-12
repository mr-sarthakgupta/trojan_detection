# -*- coding: utf-8 -*-
"""example_submission.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1YNkTM0ljT5zsaWFBuZMeXAkVa7C5jrbA
"""
from dis import dis
from math import dist
from turtle import distance
import torch
import os
import json
from tqdm import tqdm
import numpy as np
import matplotlib.pyplot as plt
from torch import nn
import torch.nn.functional as F
import torch.backends.cudnn as cudnn
cudnn.benchmark = True  # fire on all cylinders
from sklearn.metrics import roc_auc_score, roc_curve
import sys
import torchvision
from torchvision import transforms
# import logging
from platform import architecture
import zest.utils as utils
import zest.train as train
import zest.model as model
import zest.wrn as wrn
import random


sys.path.insert(0, '..')

"""## Create the dataset class"""

class NetworkDatasetDetection(torch.utils.data.Dataset):
    def __init__(self, model_folder):
        super().__init__()
        model_paths = []
        model_paths.extend([os.path.join(model_folder, 'clean', x) \
                            for x in sorted(os.listdir(os.path.join(model_folder, 'clean')))])
        model_paths.extend([os.path.join(model_folder, 'trojan', x) \
                            for x in sorted(os.listdir(os.path.join(model_folder, 'trojan')))])
        labels = []
        data_sources = []
        for p in model_paths:
            with open(os.path.join(p, 'info.json'), 'r') as f:
                info = json.load(f)
                data_sources.append(info['dataset'])
            if p.split('/')[-2] == 'clean':
                labels.append(0)
            elif p.split('/')[-2] == 'trojan':
                labels.append(1)
            else:
                raise ValueError('unexpected path {}'.format(p))
        self.model_paths = model_paths
        self.labels = labels
        self.data_sources = data_sources
    
    
    def __len__(self):
        return len(self.model_paths)
    
    def __getitem__(self, index):
        # print(f"index: {index}, path: {os.path.join(self.model_paths[index], 'model.pt')}, True/False: {os.path.isfile(os.path.join(self.model_paths[index], 'model.pt'))}")
        return torch.load(os.path.join(self.model_paths[index], 'model.pt')), self.labels[index], self.data_sources[index]

def custom_collate(batch):
    return [x[0] for x in batch], [x[1] for x in batch], [x[2] for x in batch]

"""## Load data
Spliting off a validation set from the train set for testing purposes.
"""

dataset_path = '../../tdc_datasets'
task = 'detection'
dataset = NetworkDatasetDetection(os.path.join(dataset_path, task, 'train'))

split = int(len(dataset) * 0.8)
rnd_idx = np.random.permutation(len(dataset))
train_dataset = torch.utils.data.Subset(dataset, rnd_idx[:split])
val_dataset = torch.utils.data.Subset(dataset, rnd_idx[split:])

train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=1, shuffle=True,
                                           num_workers=0, pin_memory=False, collate_fn=custom_collate)
val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=1,
                                           num_workers=0, pin_memory=False, collate_fn=custom_collate)

"""## Construct the MNTD network"""

data_sources = ['CIFAR-10', 'CIFAR-100', 'GTSRB']
# data_sources = ['CIFAR-10', 'CIFAR-100', 'GTSRB', 'MNIST']
# data_source_to_channel = {k: 1 if k == 'MNIST' else 3 for k in data_sources}
data_source_to_resolution = {k: 28 if k == 'MNIST' else 32 for k in data_sources}
data_source_to_num_classes = {'CIFAR-10': 10, 'CIFAR-100': 100, 'GTSRB': 43, 'MNIST': 10}

class MetaNetwork(nn.Module):
    def __init__(self, num_queries, num_classes=1):
        super().__init__()
        transform_to_tensor = transforms.Compose([
            transforms.ToTensor()])
        gtsrb_transform = transforms.Compose([
            transforms.Resize((32, 32)),
            transforms.ToTensor()
            ])
        # mnist = torchvision.datasets.MNIST(download=True, root = '../data/', transform = transform_to_tensor)
        gtsrb = torchvision.datasets.GTSRB(download=True, root = '../data/', transform = gtsrb_transform)
        cifar10 = torchvision.datasets.CIFAR10(download=True, root = '../data/', transform = transform_to_tensor)
        cifar100 = torchvision.datasets.CIFAR100(download=True, root = '../data/', transform = transform_to_tensor)

        # self.mnist_dataloader = torch.utils.data.DataLoader(mnist, batch_size = num_queries, shuffle = True, drop_last = True)
        self.gtsrb_dataloader = torch.utils.data.DataLoader(gtsrb, batch_size = num_queries, shuffle = True, drop_last = True)
        self.cifar10_dataloader = torch.utils.data.DataLoader(cifar10, batch_size = num_queries, shuffle = True, drop_last = True)
        self.cifar100_dataloader = torch.utils.data.DataLoader(cifar100, batch_size = num_queries, shuffle = True, drop_last = True)

        # self.mnist_train, self.mnist_test = torch.utils.data.random_split(mnist, [50000, 10000])
        self.gtsrb_train, self.gtsrb_test = torch.utils.data.random_split(gtsrb, [len(gtsrb) - 7357, 7357])
        self.cifar10_train, self.cifar10_test = torch.utils.data.random_split(cifar10, [len(cifar10) - 10000, 10000])
        self.cifar100_train, self.cifar100_test = torch.utils.data.random_split(cifar100, [len(cifar100) - 10000, 10000])

        # self.mnist_dataloader = torch.utils.data.DataLoader(self.mnist, batch_size = num_queries, shuffle = True, drop_last = True)
        self.gtsrb_dataloader = torch.utils.data.DataLoader(gtsrb, batch_size = num_queries, shuffle = True, drop_last = True)
        self.cifar10_dataloader = torch.utils.data.DataLoader(cifar10, batch_size = num_queries, shuffle = True, drop_last = True)
        self.cifar100_dataloader = torch.utils.data.DataLoader(cifar100, batch_size = num_queries, shuffle = True, drop_last = True)
                
        # for x, y in self.mnist_dataloader:
        #     mnist_samples = x
        for x, y in self.gtsrb_dataloader:
            gtsrb_samples = x
        for x, y in self.cifar10_dataloader:
            cifar10_samples = x
        for x, y in self.cifar100_dataloader:
            cifar100_samples = x
        
        self.queries = nn.ParameterDict(
            {
                # 'MNIST': nn.Parameter(mnist_samples),
                'CIFAR-10': nn.Parameter(cifar10_samples),
                'CIFAR-100': nn.Parameter(cifar100_samples),
                'GTSRB': nn.Parameter(gtsrb_samples)
            }
        )
        self.affines = nn.ModuleDict(
            {k: nn.Linear(data_source_to_num_classes[k]*num_queries, 1024) for k in data_sources}
        )
        self.norm1 = nn.LayerNorm(1024)
        self.norm2 = nn.LayerNorm(8)
        self.relu = nn.ReLU(True)
        self.layer1 = nn.Linear(1024 + 8, 512)
        self.layer2 = nn.Linear(512, 256)
        self.layer3 = nn.Linear(256, 128)
        self.layer4 = nn.Linear(128, 64)
        self.layer5 = nn.Linear(64, 32)
        self.layer6 = nn.Linear(32, 16)
        self.layer7 = nn.Linear(16, 1)
        self.flattener = nn.Flatten(start_dim = 0)
        
    def forward(self, net, data_source, dist):
        """
        :param net: an input network of one of the model_types specified at init
        :param data_source: the name of the data source
        :returns: a score for whether the network is a Trojan or not
        """
        query = self.queries[data_source]
        out = net(query)
        out = self.affines[data_source](out.view(1, -1))
        out = self.norm1(out)
        dist = torch.unsqueeze(self.flattener(dist), dim = 0)
        out = torch.cat((out, dist), dim = 1)
        out = self.relu(out)
        out = self.relu(self.layer1(out))
        out = self.relu(self.layer2(out))
        out = self.relu(self.layer3(out))
        out = self.relu(self.layer4(out))
        out = self.relu(self.layer5(out))
        out = self.relu(self.layer6(out))
        out = self.layer7(out)
        return out
        
"""## Train the network"""

meta_network = MetaNetwork(1000, num_classes=1).cuda().train()

num_epochs = 10
lr = 0.000_01
weight_decay = 0.
optimizer = torch.optim.Adam(meta_network.parameters(), lr=lr, weight_decay=weight_decay)
scheduler = torch.optim.lr_scheduler.StepLR(optimizer, 3, gamma=0.3, verbose = True)

clean_models = {}
trojan_models = {}
clean_masks = {}
trojan_masks = {}
for d in data_sources:
    if d != 'MNIST':
        clean_path = os.path.join("zest/train", f"train_{d}", "clean")
        clean_model = torch.load(os.path.join(clean_path, f"id-0000/model.pt"))
        trojan_path = os.path.join("zest/train", f"train_{d}", "trojan")
        trojan_model = torch.load(os.path.join(trojan_path, f"id-0000/model.pt"))
        if d == 'CIFAR-10':
            clean_models[d] = train.TrainFn(batch_size=1, dataset = d, architecture=clean_model, loaded_trainset = meta_network.cifar10_train, loaded_testset = meta_network.cifar10_test)
            trojan_models[d] = train.TrainFn(batch_size=1, dataset = d, architecture=trojan_model, loaded_trainset = meta_network.cifar10_train, loaded_testset = meta_network.cifar10_test)
        if d == 'CIFAR-100':
            clean_models[d] = train.TrainFn(batch_size=1, dataset = d, architecture=clean_model, loaded_trainset = meta_network.cifar100_train, loaded_testset = meta_network.cifar100_test)
            trojan_models[d] = train.TrainFn(batch_size=1, dataset = d, architecture=trojan_model, loaded_trainset = meta_network.cifar100_train, loaded_testset = meta_network.cifar100_test)
        if d == 'GTSRB':
            clean_models[d] = train.TrainFn(batch_size=1, dataset = d, architecture=clean_model, loaded_trainset = meta_network.gtsrb_train, loaded_testset = meta_network.gtsrb_test)
            trojan_models[d] = train.TrainFn(batch_size=1, dataset = d, architecture=trojan_model, loaded_trainset = meta_network.gtsrb_train, loaded_testset = meta_network.gtsrb_test)
                
        clean_models[d].lime()
        trojan_models[d].lime()
        clean_masks[d] = clean_models[d].lime_mask
        trojan_masks[d] = trojan_models[d].lime_mask
dist = ['1', '2', 'inf', 'cos']


loss_ema = np.inf
for epoch in range(num_epochs):
    
    pbar = tqdm(train_loader)
    pbar.set_description(f"Epoch {epoch + 1}")
    for i, (net, label, data_source) in enumerate(pbar):
        if data_source != ['MNIST']:
            og_net = net[0]
            net = net[0]
            label = label[0]
            data_source = data_source[0]
            net.cuda().eval()
            if data_source == 'CIFAR-10':
                d_train = meta_network.cifar10_train
                d_test = meta_network.cifar10_test
                train_fn_given_model = train.TrainFn(batch_size=1, dataset = data_source, architecture=net, loaded_trainset = d_train, loaded_testset = d_test)
            elif data_source == 'CIFAR-100':
                d_train = meta_network.cifar100_train
                d_test = meta_network.cifar100_test
                train_fn_given_model = train.TrainFn(batch_size=1, dataset = data_source, architecture=net, loaded_trainset = d_train, loaded_testset = d_test)
            elif data_source == 'GTSRB':
                d_train = meta_network.gtsrb_train
                d_test = meta_network.gtsrb_test
                train_fn_given_model = train.TrainFn(batch_size=1, dataset = data_source, architecture=net, loaded_trainset = d_train, loaded_testset = d_test)
            distance_list = []
            train_fn_given_model.lime()
            a = train_fn_given_model.lime_mask
            distance_list.append(np.array(utils.parameter_distance(clean_masks[data_source], a, order=dist, lime=True)))
            distance_list.append(np.array(utils.parameter_distance(trojan_masks[data_source], a, order=dist, lime=True)))
            og_net.cuda().eval()
            dist_tensor = torch.tensor(np.array(distance_list)).cuda()
            dist_tensor.requires_grad = False
            out = meta_network(og_net, data_source, torch.tensor(np.array(distance_list)).to('cuda:0').float())
            loss = F.binary_cross_entropy_with_logits(out, torch.FloatTensor([label]).unsqueeze(0).cuda().float())
            optimizer.zero_grad()
            loss.backward(inputs=list(meta_network.parameters()))
            optimizer.step()
            for k in meta_network.queries.keys():
                meta_network.queries[k].data = meta_network.queries[k].data.clamp(0, 1)
            loss_ema = loss.item() if loss_ema == np.inf else 0.95 * loss_ema + 0.05 * loss.item()

            pbar.set_postfix(loss=loss_ema)
    scheduler.step()
    torch.save(meta_network, "meta_network_withoutnorm.pt")

meta_network.eval()

"""## Evaluate the network"""

def evaluate(meta_network, loader):
    loss_list = []
    correct_list = []
    confusion_matrix = torch.zeros(2,2)
    all_scores = []
    all_labels = []
    
    for i, (net, label, data_source) in enumerate(tqdm(loader)):
        net[0].cuda().eval()
        if data_source != ['MNIST']:
            data_source = data_source[0]
            og_net = net[0]
            if data_source == 'CIFAR-10':
                d_train = meta_network.cifar10_train
                d_test = meta_network.cifar10_test
                train_fn_given_model = train.TrainFn(batch_size=1, dataset = data_source, architecture=net[0], loaded_trainset = d_train, loaded_testset = d_test)
            elif data_source == 'CIFAR-100':
                d_train = meta_network.cifar100_train
                d_test = meta_network.cifar100_test
                train_fn_given_model = train.TrainFn(batch_size=1, dataset = data_source, architecture=net[0], loaded_trainset = d_train, loaded_testset = d_test)
            elif data_source == 'GTSRB':
                d_train = meta_network.gtsrb_train
                d_test = meta_network.gtsrb_test
                train_fn_given_model = train.TrainFn(batch_size=1, dataset = data_source, architecture=net[0], loaded_trainset = d_train, loaded_testset = d_test)
            distance_list = []
            train_fn_given_model.lime()
            a = train_fn_given_model.lime_mask
            distance_list.append(np.array(utils.parameter_distance(clean_masks[data_source], a, order=dist, lime=True)))
            distance_list.append(np.array(utils.parameter_distance(trojan_masks[data_source], a, order=dist, lime=True)))
            og_net.cuda().eval()
            with torch.no_grad():
                out = meta_network(og_net, data_source, torch.tensor(np.array(distance_list)).to('cuda:0').float())
            loss = F.binary_cross_entropy_with_logits(out, torch.FloatTensor([label[0]]).unsqueeze(0).cuda())
            correct = int((out.squeeze() > 0).int().item() == label[0])
            loss_list.append(loss.item())
            correct_list.append(correct)
            confusion_matrix[(out.squeeze() > 0).int().item(), label[0]] += 1
            all_scores.append(out.squeeze().item())
            all_labels.append(label[0])
    
    return np.mean(loss_list), np.mean(correct_list), confusion_matrix, all_labels, all_scores

loss, acc, cmat, _, _ = evaluate(meta_network, train_loader)
print(f'Train Loss: {loss:.3f}, Train Accuracy: {acc*100:.2f}')
print('Confusion Matrix:\n', cmat.numpy())

loss, acc, cmat, all_labels, all_preds = evaluate(meta_network, val_loader)
print(f'Val Loss: {loss:.3f}, Val Accuracy: {acc*100:.2f}')
print('Confusion Matrix:\n', cmat.numpy())

print(f'Val AUROC: {roc_auc_score(all_labels, all_preds):.3f}')

"""## Make submission"""

# Dataset class for the validation/test sets, which contain all networks in a single folder

class NetworkDatasetDetectionTest(torch.utils.data.Dataset):
    def __init__(self, model_folder):
        super().__init__()
        model_paths = [os.path.join(model_folder, x) for x in sorted(os.listdir(os.path.join(model_folder)))]
        data_sources = []
        for model_path in model_paths:
            with open(os.path.join(model_path, 'info.json'), 'r') as f:
                info = json.load(f)
                data_sources.append(info['dataset'])
        self.model_paths = model_paths
        self.data_sources = data_sources
    
    def __len__(self):
        return len(self.model_paths)
    
    def __getitem__(self, index):
        return torch.load(os.path.join(self.model_paths[index], 'model.pt')), self.data_sources[index]

def custom_collate(batch):
    return [x[0] for x in batch], [x[1] for x in batch]

dataset_path = '../../tdc_datasets'
task = 'detection'

test_dataset = NetworkDatasetDetectionTest(os.path.join(dataset_path, task, 'val'))
test_loader = torch.utils.data.DataLoader(test_dataset, batch_size=1, shuffle=False,
                                          num_workers=0, pin_memory=False, collate_fn=custom_collate)

# def predict(meta_network, loader):
    
#     all_scores = []
#     for i, (net, data_source) in enumerate(tqdm(loader)):
#         net[0].cuda().eval()
#         with torch.no_grad():
#             out = meta_network(net[0], data_source[0])
#         all_scores.append(out.squeeze().item())
    
#     return all_scores

# scores = predict(meta_network, test_loader)

# if not os.path.exists('mntd_submission'):
#     os.makedirs('mntd_submission')

# with open(os.path.join('mntd_submission', 'predictions.npy'), 'wb') as f:
#     np.save(f, np.array(scores))
