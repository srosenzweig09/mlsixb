"""
This program trains a neural network with hyperparameters that are read from a
user-specified configuration file. The user may also provide a hyperparameter
and value to override the configuration file.
"""

print("Loading libraries. May take a few minutes.")

import awkward as ak
import numpy as np
import os
import vector
vector.register_awkward()
from argparse import ArgumentParser
from configparser import ConfigParser
from keras.models import Sequential
from keras.layers import Dense, Dropout
from keras.callbacks import EarlyStopping
from keras.regularizers import l1, l2, l1_l2
from keras.constraints import max_norm
from pandas import DataFrame
from sixb import get_sixb_p4, get_6jet_p4, get_background_p4
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from tensorflow import compat
from tqdm import tqdm
from sys import argv
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2' # suppress Keras/TF warnings
compat.v1.logging.set_verbosity(compat.v1.logging.ERROR) # suppress Keras/TF warnings

# Custom libraries and modules
from colors import CYAN, W
from kinematics import calcDeltaR
from logger import info, error

print("Libraries loaded.")
print()


### ------------------------------------------------------------------------------------
## Implement command line parser

info("Parsing command line arguments.")

parser = ArgumentParser(description='Command line parser of model options and tags')

parser.add_argument('--type', dest = 'type', help = 'parton, smeared, or reco' , default = 'reco' )
parser.add_argument('--task', dest = 'task', help = 'classifier or regressor'  , default = 'classifier' )
parser.add_argument('--run' , dest = 'run' , help = 'index of training session', default = 1 )
parser.add_argument('--tag' , dest = 'tag' , help = 'special tag', default = None )

args = parser.parse_args()

### ------------------------------------------------------------------------------------
## Prepare output directories

out_dir = f"models/{args.task}/{args.type}/"
if args.tag:
    out_dir += f'{args.tag}/'
model_dir = out_dir + "model/"

if not os.path.exists(out_dir):
    os.makedirs(out_dir)
if not os.path.exists(model_dir):
    os.makedirs(model_dir)

# info(f"Training sessions will be saved in {model_dir}")

### ------------------------------------------------------------------------------------
## Import configuration file

assert (args.type == 'parton') or (args.type == 'smeared') or (args.type == 'reco'), "--type must be 'parton', 'smeared', or 'reco'!"

cfg_location = 'config/'
cfg_name = f'{args.task}/{args.type}.cfg'

cfg = cfg_location + cfg_name

info(f"Loading configuration file from {cfg}")

# Load the configuration using configparser
config = ConfigParser()
config.optionxform = str
config.read(cfg)

# Hidden hyperparameters
hidden_activations = config['HIDDEN']['HiddenActivations']
nodes              = config['HIDDEN']['Nodes'].split('\n')
nlayers            = len(nodes)

# Output hyperparameters
output_activation  = config['OUTPUT']['OutputActivation']
output_nodes       = int(config['OUTPUT']['OutputNodes'])

# Fitting hyperparameters
optimizer          = config['OPTIMIZER']['OptimizerFunction']
loss_function      = config['LOSS']['LossFunction']
nepochs            = int(config['TRAINING']['NumEpochs'])
batch_size         = int(config['TRAINING']['BatchSize'])
    
inputs_filename    = config['INPUTS']['InputFile']
if args.tag:
    inputs_filename = f'inputs/reco/nn_input_MX700_MY400_classifier_{args.tag}.npz'

nn_type            = config['TYPE']['Type']

# info(f"Loading inputs from file:\n\t{CYAN}{inputs_filename}{W}")
signal_p4, background_p4, sixb_ids, sixb_btag, bkgd_btag, nbkgd = get_6jet_p4() # FIXME Will have to add a filename later.
# background_p4s = get_background_p4()
info("p4s loaded.")

# combos_2 = ak.combinations(signal_p4, 2)
# lefts, rights = ak.unzip(combos_2)
# sixb_deltaR = lefts.deltaR(rights)
combos_6 = ak.combinations(signal_p4, 6)
part0, part1, part2, part3, part4, part5 = ak.unzip(combos_6)
evt_sixb_p4 = part0 + part1 + part2 + part3 + part4 + part5

# combos_2 = ak.combinations(background_p4, 2)
# lefts, rights = ak.unzip(combos_2)
# bkgd_deltaR = lefts.deltaR(rights)
combos_6 = ak.combinations(background_p4, 6)
part0, part1, part2, part3, part4, part5 = ak.unzip(combos_6)
evt_bkgd_p4 = part0 + part1 + part2 + part3 + part4 + part5

# output_activation = 'sigmoid' # allows for multiple 'true' assignments
output_nodes = 2

inputs = []
for p4, btag, evt_p4 in tqdm(zip(signal_p4, sixb_btag, evt_sixb_p4)):
    in_arr = [p4.pt, p4.eta, p4.phi, btag, evt_p4.pt]
    inputs.append(in_arr)
for p4, btag, evt_p4 in tqdm(zip(background_p4, bkgd_btag, evt_bkgd_p4)):
    in_arr = [p4.pt, p4.eta, p4.phi, btag, evt_p4.pt]
    inputs.append(in_arr)
for i,features in enumerate(inputs):
    inputs[i] = np.concatenate((features))
inputs = np.array((inputs))
print(inputs.shape)

targets = np.concatenate((np.repeat(1, len(signal_p4)), np.repeat(0, len(background_p4))))
targets2 = np.where(targets == 1, 0, 1)
targets = np.column_stack((targets, targets2))
print(targets.shape)

### ------------------------------------------------------------------------------------
## 

scaler = MinMaxScaler()
scaler.fit(inputs)
x = scaler.transform(inputs)

test_size = 0.20
val_size = 0.125
X_train, X_test, x_train, x_test, y_train, y_test = train_test_split(inputs, x, targets, test_size=test_size)
x_train, x_val, y_train, y_val = train_test_split(x_train, y_train, test_size=val_size)

# Save training examples
np.savez("training_examples.npz", x_test=X_test, y_test=y_test, x_train=X_train, y_train=y_train, sixb_ids=sixb_id, nbkgd=nbkgd)

# Load training examples
# examples = np.load(inputs_filename)
# x_train = examples['x_train']
# x_test = examples['x_test']
# x_val = examples['x_val']

# y_train = examples['y_train']
# y_test = examples['y_test']
# y_val = examples['y_val']

# param_dim = x_train.shape[1]
param_dim = np.shape(inputs)[1]

### ------------------------------------------------------------------------------------
## 

info("Defining the model.")
# Define the keras model
model = Sequential()

# Input layers
model.add(Dense(nodes[0], input_dim=param_dim, activation=hidden_activations))

# # Hidden layers
for i in range(1,nlayers):
    if args.task == 'classifier':
        model.add(Dense(int(nodes[i]), activation=hidden_activations, kernel_constraint=max_norm(1.0), kernel_regularizer=l1_l2(), bias_constraint=max_norm(1.0)))
    elif args.task == 'regressor':
        model.add(Dense(int(nodes[i]), activation=hidden_activations, kernel_regularizer=l1_l2()))

# Output layer
model.add(Dense(output_nodes, activation=output_activation))

# Stop after epoch in which loss no longer decreases but save the best model.
es = EarlyStopping(monitor='loss', restore_best_weights=True)

if args.task == 'classifier':
    met = ['accuracy']
elif args.task == 'regressor':
    met = None

info("Compiling the model.")
model.compile(loss=loss_function, 
              optimizer=optimizer, 
              metrics=met)

# Make a list of the hyperparameters and print them to the screen.
nn_info_list = [
    f"Input parameters:            {param_dim},\n",
    f"Optimizer:                   {optimizer}\n",
    f"Loss:                        {loss_function}\n",
    f"Num epochs:                  {nepochs}\n",
    f"Batch size:                  {batch_size}\n",
    f"Num hidden layers:           {nlayers}\n",
    f"Input activation function:   {hidden_activations}\n",
    f"Hidden layer nodes:          {nodes}\n",
    f"Hidden activation functions: {hidden_activations}\n",
    f"Num output nodes:            {output_nodes}\n",
    f"Output activation function:  {output_activation}"]

for line in nn_info_list:
    print(line)

### ------------------------------------------------------------------------------------
## Fit the model

print()
info("Preparing to fit the model!\n")
info(f"Training with {len(x_train)} examples")

# fit the keras model on the dataset
history = model.fit(x_train,
                    y_train, 
                    validation_data=(x_val, y_val), 
                    epochs=nepochs, 
                    batch_size=batch_size, 
                    callbacks=[es])

### ------------------------------------------------------------------------------------
## Apply the model (predict)

scores = model.predict(x_test)
print(scores)
print(scores.shape)

### ------------------------------------------------------------------------------------
## Save the model, history, and predictions

np.savez(out_dir + f"scores_{args.run}", scores=scores)

# convert the history.history dict to a pandas DataFrame   
hist_df = DataFrame(history.history) 

# Save to json:  
hist_json_file = model_dir + f'history_{args.run}.json' 

with open(hist_json_file, mode='w') as f:
    hist_df.to_json(f)

# Save model to json and weights to h5
model_json = model.to_json()

json_save = model_dir + f"model_{args.run}.json"
h5_save   = json_save.replace(".json", ".h5")

with open(json_save, "w") as json_file:
    json_file.write(model_json)

# serialize weights to HDF5
model.save_weights(h5_save)

info(f"Saved model and history to disk in location:"
      f"\n   {json_save}\n   {h5_save}\n   {hist_json_file}")


### ------------------------------------------------------------------------------------
## 

nn_info_list[3] = f"Num epochs:                  {len(hist_df)}\n"

with open(out_dir + 'nn_info.txt', "w") as f:
    for line in nn_info_list:
        f.writelines(line)

print("-"*45 + CYAN + " Training ended " + W + "-"*45)