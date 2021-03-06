from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.layers import Embedding, LSTM, Dense, Dropout, BatchNormalization, Lambda
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.models import Sequential, model_from_json
from tensorflow.keras.optimizers import Adam
import tensorflow.keras.utils as ku
import numpy as np
import re
import pprint as pp
import warnings
import matplotlib
import matplotlib.pyplot as plt
from math import log
import sys
import os
warnings.filterwarnings('ignore')



# Note: num_words does NOT reduce the size of the dictionary on its own; see
# https://github.com/keras-team/keras/issues/8092#issuecomment-372833486
""" This definition is if handling UNK words """
# total_words = 5000
# tokenizer = Tokenizer(lower = False, oov_token = 'UNK', filters = '!"#$%&()*+,./:;<=>?@\\^_`{|}~\t\n', num_words = total_words)
""" End """
tokenizer = Tokenizer(lower = False, oov_token = 'UNK', filters = '!"#$%&()+,/:;<=>?@\\^_`{|}~\t\n')
# tokenizer = Tokenizer()
def sentencise(text):
	dump = ""
	line = text.readline()
	while(line):
		line = re.sub('\.\.\.', ' eos', line)
		dump = dump + line + ' '
		line = text.readline()
	return dump

def dataset_preparation(data):
	# basic cleanup
	corpus = data.lower().split("\n")
	# tokenization
	tokenizer.fit_on_texts(corpus)
	total_words = len(tokenizer.word_index)


	""" Fragment below is for handling unknown words """
	# getting rid of infrequent words
	# pp.pprint(tokenizer.word_index)
	# KEY STEP FOR HANDLING UNK
	# tokenizer.word_index = {e:i for e,i in tokenizer.word_index.items() if i < total_words}
	# tokenizer.word_index[tokenizer.oov_token] = total_words
	# pp.pprint(len(tokenizer.word_index))
	# pp.pprint(tokenizer.texts_to_sequences(corpus))
	""" End """

	# create input sequences using list of tokens
	input_sequences = []
	for line in corpus:
		token_list = tokenizer.texts_to_sequences([line])[0]
		for i in range(1, len(token_list)):
			n_gram_sequence = token_list[:i+1]
			input_sequences.append(n_gram_sequence)

	# pad sequences
	max_sequence_len = max([len(x) for x in input_sequences])
	input_sequences = np.array(pad_sequences(input_sequences, maxlen=max_sequence_len, padding='pre'))

	# create predictors and label
	predictors, label = input_sequences[:,:-1],input_sequences[:,-1]
	label = ku.to_categorical(label, num_classes=total_words+1)

	return predictors, label, max_sequence_len, total_words

def create_model(predictors, label, max_sequence_len, total_words):

	model = Sequential()
	model.add(Embedding(total_words+1, 10, input_length=max_sequence_len-1))
	model.add(LSTM(512,
			  activation = 'tanh',
			  recurrent_activation = 'hard_sigmoid',
			  recurrent_dropout=0.0,
			  dropout = 0.2,
			  return_sequences = True))
	model.add(BatchNormalization())
	model.add(LSTM(512,
			  activation = 'tanh',
			  recurrent_activation = 'hard_sigmoid',
			  recurrent_dropout=0.0,
			  dropout = 0.2,
			  return_sequences = False))
	model.add(BatchNormalization())
	model.add(Dropout(0.5))
	# Temperature
	model.add(Lambda(lambda x: x / 0.8))
	model.add(Dense(total_words+1, activation='softmax'))

	try:
		model = ku.multi_gpu_model(model)
	except:
		pass

	model.compile(loss='categorical_crossentropy',
				  optimizer=Adam(lr = 2e-3),
				  metrics=['accuracy'])
	# earlystop = EarlyStopping(monitor='val_loss', min_delta=1, patience=5, verbose=0, mode='auto')
	h = model.fit(predictors,
				  label,
				  epochs=1,
				  verbose=1,
				  batch_size=1024,
				  validation_split = 0.2)
	print(model.summary())
	# summarize history for accuracy
	fig = plt.figure()
	plt.plot(h.history['acc'], '-go')
	plt.title('model accuracy')

	plt.ylabel('accuracy')
	plt.xlabel('epoch')
	# plt.show()
	fig.savefig('accuracy_plot.png')
	# from IPython.display import Image
	# Image('accuracy_plot.png')

	fig = plt.figure()
	plt.plot(h.history['loss'], '-ro')
	plt.title('model loss')
	plt.ylabel('loss')
	plt.xlabel('epoch')
	# plt.show()
	fig.savefig('loss_plot.png')
	# from IPython.display import Image
	# Image('loss_plot.png')

	return model

def generate_text(model, seed_text, next_words, max_sequence_len):
	for _ in range(next_words):
		# Tokenize current predicted sequence and pad it
		token_list = tokenizer.texts_to_sequences([seed_text])[0]
		# print(token_list)
		token_list = pad_sequences([token_list], maxlen=max_sequence_len-1, padding='pre')
		# Use model to predict next word
		predicted = model.predict_classes(token_list, verbose=0)

		output_word = ""
		for word, index in tokenizer.word_index.items():
			if index == predicted:
				output_word = word
				break

		seed_text += " " + output_word
	seed_text = re.sub(' eos', '...', seed_text)
	seed_text = '...'.join(i.strip().capitalize() for i in seed_text.split('...'))
	return seed_text

def save_model(filename, weights, model):
	model_json = model.to_json()
	with open(filename, "w+") as json_file:
	    json_file.write(model_json)
	# serialize weights to HDF5
	model.save_weights(weights)
	print("Saved model to disk")

def load_model(filename, weights):
	json_file = open(filename, 'r')
	loaded_model_json = json_file.read()
	json_file.close()
	model = model_from_json(loaded_model_json)
	# load weights into new model
	model.load_weights(weights)
	print("Loaded model from disk")
	return model

def wordListToFreqDict(wordlist):
    wordfreq = [wordlist.count(p) for p in wordlist]
    return dict(list(zip(wordlist,wordfreq)))


""" MAIN
Train bit moved to train_waffler.py
Test bit (generation) moved to waffler.py
"""
try:
	# choice = input"Choose model (origin/speakers)\n")
	choice = "origin"
	rel_path = re.sub(r'[^/]+$', '', os.getcwd())
	data_path = os.path.join(rel_path, 'data/trainData/')
	model_path = os.path.join(rel_path, 'models/')

	if choice == 'origin':
		model_choice = (os.path.join(model_path, 'conv_model_origin.json'),
					   os.path.join(model_path, 'conv_model_origin.h5'))
		data = open(os.path.join(data_path, 'train_origin.txt'))
	elif choice == 'speakers':
		model_choice = (os.path.join(model_path, 'conv_model_speakers.json'),
					   os.path.join(model_path, 'conv_model_speakers.h5'))
		data = open(os.path.join(data_path, 'train_speakers.txt'))
	else:
		raise Exception("An error occured")
except:
	print("Error; to run correctly, supply 1 argument from {origin, speakers}")
	exit()

# data = sentencise(data)
# predictors, label, max_sequence_len, total_words = dataset_preparation(data)
# model = create_model(predictors, label, max_sequence_len, total_words)
# save_model(model_choice[0], model_choice[1], model)
