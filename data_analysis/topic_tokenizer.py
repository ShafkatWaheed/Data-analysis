import re
import array
import string
import numpy as np
import scipy.sparse

import lda

from collections import defaultdict, Counter
from nltk.corpus import stopwords
# from nltk.stem import SnowballStemmer
from nltk.tokenize.casual import TweetTokenizer

from data_analysis._util import make_document_term_matrix

class LDAModel:
    def __init__(self, token_list=None, n_topics=20):
        self.vocabulary = defaultdict()
        self.vocabulary.default_factory = self.vocabulary.__len__
        self._model = lda.LDA(n_topics=n_topics,
                              n_iter=1500,
                              random_state=1)

        if token_list:
            self.train_model(token_list)

        self.token_list = []

    def train_model(self, token_list=None):
        if token_list is None:
            token_list = self.token_list
            self.token_list = []

        doc_term = self._make_document_term_matrix(token_list)
        self._model.fit(doc_term)

        return self.predict(doc_term)

    def set_number_topics(self, n_topics):
        self._model.n_topics = n_topics

    def get_vocabulary_helper(self, topic_numbers, number=8):
        # TODO: think of a better way to do this.
        vocab = np.array(list(self.vocabulary.keys()))
        topic_models = self._model.components_
        result = []
        for topic_number in topic_numbers:
            words = vocab[np.argsort(topic_models[topic_number])][:-(number+1):-1]
            result.append(words)

        return result

    def predict(self, document_term=None, token_list=None):
        """
        returns a numpy array of the predicted topic
        """
        if document_term is None:
            doucment_term = self._make_document_term_matrix(token_list)

        return self._model.transform(document_term).argmax(1)

    def _make_document_term_matrix(self, token_list):
        j_indices = []
        """Construct an array.array of a type suitable for scipy.sparse indices."""
        indptr = array.array(str("i"))
        values = array.array(str("i"))
        indptr.append(0)

        for tokens in token_list:
            feature_counter = {}
            for token in tokens:
                feature_idx = self.vocabulary[token]
                if feature_idx not in feature_counter:
                    feature_counter[feature_idx] = 1
                else:
                    feature_counter[feature_idx] += 1
            j_indices.extend(feature_counter.keys())
            values.extend(feature_counter.values())
            indptr.append(len(j_indices))

        vocabulary = dict(self.vocabulary)
        j_indices = np.asarray(j_indices, dtype=np.intc)
        indptr = np.frombuffer(indptr, dtype=np.intc)
        values = np.frombuffer(values, dtype=np.intc)

        X = scipy.sparse.csr_matrix((values, j_indices, indptr),
                           shape=(len(indptr) - 1, len(vocabulary)),
                           dtype=np.int64)
        X.sort_indices()
        return X


class TopicTokenizer(TweetTokenizer):
    STOP = set(stopwords.words('english'))
    def __init__(self,
                 preserve_case=False,
                 reduce_len=True,
                 remove_url=True,
                 transform_handles=True,
                 stem_words=True):

        super().__init__(preserve_case,
                         reduce_len,
                         False)

        self.remove_url = remove_url
        self.transform_handles = transform_handles
        self.stem_words = stem_words
        # self._stemmer = SnowballStemmer('english')
        self.STOP.update(('...', '…', '..', 'rt', '10', '11', '12', "i'll",
                          'ill', 'that', "you'r", 'ur', 'u', 'lol', 'one',
                          "don't", "i'm", 'lmao', 'omg', 'im', "you're", 'oh',
                          'im', 'yall', "y'all", "you'll", 'that', 'didnt',
                          "didn't", 'idk', "i've", 'w', "you're", 'ok',
                          "isn't", "she's", "it's", "who's", "he's", "that's",
                          "thats'", "what's", "there's", "whats'", "thats'",
                          "here's", "how's", "others", "one's", 'like', 'tho', 'lot', 'tbh',))

        # https://github.com/nltk/nltk/blob/develop/nltk/tokenize/casual.py#L327
        self.twitter_handle_re = re.compile(r"(?<![A-Za-z0-9_!@#\$%&*])@(([A-Za-z0-9_]){20}(?!@))|(?<![A-Za-z0-9_!@#\$%&*])@(([A-Za-z0-9_]){1,19})(?![A-Za-z0-9_]*@)")

        # https://gist.github.com/uogbuji/705383
        self.url_re = re.compile(r'(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'".,<>?\xab\xbb\u201c\u201d\u2018\u2019]))')

    def fix_handles(self, text):
        return self.twitter_handle_re.sub('', text)

    def handle_urls(self, text):
        return self.url_re.sub('', text)

    def stem(self, words):
        # stemmed = [self._stemmer.stem(word)
        stemmed = [word
                   for word in words
                   if not (word in string.punctuation
                           or word in self.STOP
                           or len(word) == 1)]

        return stemmed

    def flat_tokenized_list(self, texts: list):
        token_list = [self.tokenize(t) for t in texts]
        return [t for tokens in token_list for t in tokens if t]

    def tokenize(self, text):
        # Text preprocessing
        if self.remove_url:
            text = self.handle_urls(text)
        if self.transform_handles:
            text = self.fix_handles(text)

        words = super().tokenize(text)
        if self.stem_words:
            words = self.stem(words)

        return words
