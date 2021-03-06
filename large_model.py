import tensorflow as tf
from keras.models import Model
from keras.layers import Dense, Dropout, Embedding, LSTM, Input, TimeDistributed, Activation
from keras.optimizers import Adam,SGD
import keras.backend as K
import numpy as np


class LargeLanguageModel(object):
    def __init__(self,params):
        config = tf.ConfigProto(allow_soft_placement=True)
        self.sess = tf.Session(config = config)
        K.set_session(self.sess)
        # Pull out all of the parameters
        self.batch_size = params['batch_size']
        self.seq_len = params['seq_len']
        self.vocab_size = params['vocab_size']
        self.embed_size = params['embed_size']
        self.hidden_dim = params['hidden_dim']
        self.num_layers = params['num_layers']
        current_gpu = 0
        with tf.device('/gpu:' + str(current_gpu)):
            current_gpu += 1
            # Set up the input placeholder
            self.input_seq = tf.placeholder(tf.float32, shape=[None, self.seq_len])
            # Build the RNN
            self.rnn = Embedding(self.vocab_size + 1, self.embed_size, input_length=self.seq_len)(self.input_seq)
        print 'Adding LSTM layers to gpu ' + str(current_gpu)
        with tf.device('/gpu:' + str(current_gpu)):
            self.rnn = LSTM(output_dim=2048, return_sequences=True, name='rnn_1')(self.rnn)
            current_gpu += 1
            self.rnn = LSTM(output_dim=self.hidden_dim, return_sequences=True, name='rnn_1')(self.rnn)
        with tf.device('/gpu:' + str(current_gpu)):
            print 'Adding output layer to gpu ' + str(current_gpu)
            current_gpu += 1
            rnn_output = tf.unpack(self.rnn, axis=1)
            self.w_proj = tf.Variable(tf.zeros([self.vocab_size, self.hidden_dim]),dtype=tf.float32)
            self.b_proj = tf.Variable(tf.zeros([self.vocab_size]),dtype=tf.float32)
            self.output_seq = tf.placeholder(tf.int32, shape=([None, self.seq_len]))
            losses = []
            outputs = []
            for t in range(self.seq_len):
                rnn_t = rnn_output[t]
                y_t = tf.reshape(self.output_seq[:, t],[-1,1])
                step_loss = tf.nn.sampled_softmax_loss(weights=self.w_proj, biases=self.b_proj, inputs=rnn_t,
                                                       labels=y_t, num_sampled=512, num_classes=self.vocab_size)
                losses.append(step_loss)
                outputs.append(tf.matmul(rnn_t, tf.transpose(self.w_proj)) + self.b_proj)
            self.step_losses = losses
            self.output = outputs
            self.loss = tf.reduce_mean(self.step_losses)
        with tf.device('/gpu:' + str(current_gpu)):
            print 'Adding softmax layer to gpu ' + str(current_gpu)
            self.softmax = tf.nn.softmax(self.output)
    def compile(self,lr=1e-3):
        self.loss_function = tf.reduce_mean(self.loss)
        self.opt = tf.train.AdamOptimizer(lr).minimize(self.loss_function)
        self.sess.run(tf.initialize_all_variables())
    def train_on_batch(self,X_batch,Y_batch):
        _, loss_value = self.sess.run([self.opt, self.loss],feed_dict={self.input_seq: X_batch, self.output_seq: Y_batch})
        return loss_value
    def predict(self,X,asarray=True):
        preds = self.sess.run(self.softmax, feed_dict={self.input_seq: X})
        if asarray:
            preds = np.asarray(preds)
            ## Make dimensions more sensible ##
            preds = np.swapaxes(preds,0,1)
        return preds
    def evaluate(self,X,Y,normalize=False):
        preds = self.sess.run(self.softmax, feed_dict={self.input_seq: X})
        preds = np.asarray(preds)
        preds = np.swapaxes(preds, 0, 1)
        log_prob = 0.
        n_tokens = 0.
        ## Note we're only going to use the non-zero entries ##
        for i in range(len(X)):
            for j in range(len(X[i])):
                if X[i,j] != 0:
                    correct_prob = preds[i,j,Y[i,j]]
                    log_prob += np.log(correct_prob)
                    n_tokens += 1.
        return log_prob, n_tokens
    def generate(self,seed='',temperature=1.0):
        pass
    def save(self,save_path='./'):
        saver = tf.train.Saver()
        save_path = saver.save(self.sess, save_path + 'model.ckpt')
        print("Model saved in file: %s" % save_path)

    def load(self,save_path='./'):
        saver = tf.train.Saver()
        saver.restore(self.sess, save_path + 'model.ckpt')
        print("Model restored.")

