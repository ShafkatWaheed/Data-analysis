import os
import re
import pickle
import random

import nltk
from nltk.corpus import TwitterCorpusReader
from nltk.corpus.util import LazyCorpusLoader
from nltk.classify import NaiveBayesClassifier
from nltk.tokenize.casual import TweetTokenizer, EMOTICON_RE
from nltk.stem import SnowballStemmer


class SpecialTokenizer(TweetTokenizer):
    def __init__(self,
                 preserve_case=False,
                 reduce_len=True,
                 remove_url=True,
                 transform_handles=True,
                 stem_words=True):

        # default the strip handel to be false so we don't trigger it
        super().__init__(preserve_case=preserve_case,
                         reduce_len=reduce_len,
                         strip_handles=False)

        self.remove_url = remove_url
        self.transform_handles = transform_handles
        self.stem_words = stem_words
        self._stemmer = SnowballStemmer('english')

    def tokenize(self, text):
        # Text preprocessing
        if self.remove_url:
            text = self.handle_urls(text)
        # Text preprocessing
        if self.transform_handles:
            text = self.fix_handles(text)

        words = super().tokenize(text)
        if self.stem_words:
            words = self.stem(words)

        return words

    def stem(self, words):
        return [self._stemmer.stem(word) for word in words]

    def handle_urls(self, text):
        # https://gist.github.com/uogbuji/705383
        pattern = re.compile(r'(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'".,<>?\xab\xbb\u201c\u201d\u2018\u2019]))')
        return pattern.sub('__url', text)

    def fix_handles(self, text):
        # https://github.com/nltk/nltk/blob/develop/nltk/tokenize/casual.py#L327
        pattern = re.compile(r"(?<![A-Za-z0-9_!@#\$%&*])@(([A-Za-z0-9_]){20}(?!@))|(?<![A-Za-z0-9_!@#\$%&*])@(([A-Za-z0-9_]){1,19})(?![A-Za-z0-9_]*@)")

        return pattern.sub('__handle', text)


def make_extract_features_func(all_features):
    def inner(words_list):
        words = set(words_list)
        features = {}
        for word in words:
            key = 'contains({})'.format(word)
            value = word in all_features
            features[key] = value
        return features

    return inner

def get_classifier_filepath():
    directory = os.path.abspath(os.path.dirname(__file__))
    classifier_filepath = os.path.join(directory,
                                       'data',
                                       'naive_bayes_model.pickle')

    return classifier_filepath


def get_master_wordlist_filepath():
    directory = os.path.abspath(os.path.dirname(__file__))
    master_wordlist_fp= os.path.join(directory,
                                     'data',
                                     'master_wordlist.pickle')

    return master_wordlist_fp


def make_classifier():
    positive_file = 'positive_tweets.json'
    negative_file = 'negative_tweets.json'
    # THE FILES ARE IN THE COMPUTER
    files = [positive_file, negative_file]

    twitter_samples = LazyCorpusLoader('twitter_samples',
                                       TwitterCorpusReader,
                                       files,
                                       word_tokenizer=SpecialTokenizer(stem_words=False))

    # this returns a list of tokenized tweets, as a list of lists
    tokenized = twitter_samples.tokenized()

    # We need to unpack the `tokenized` list of lists 
    # We'll do it using a nested list comprehension
    frequency_dist = nltk.FreqDist(i for sub in tokenized for i in sub)
    frequency_dist.pprint(100)
    master_wordlist = tuple(frequency_dist.keys())

    extract_features = make_extract_features_func(master_wordlist)

    positive_tokens = twitter_samples.tokenized(positive_file)
    positive_tokens = [(tokens, 'positive') for tokens in positive_tokens]
    negative_tokens = twitter_samples.tokenized(negative_file)
    negative_tokens = [(tokens, 'negative') for tokens in negative_tokens]

    all_tokens = positive_tokens + negative_tokens
    random.shuffle(all_tokens)

    training_set = nltk.classify.apply_features(extract_features,
                                                all_tokens)

    classifier = NaiveBayesClassifier.train(training_set)

    return classifier, master_wordlist


def main():
    classifier, master_wordlist = make_classifier()
    print(classifier.show_most_informative_features())

    classifier_filepath = get_classifier_filepath()
    if os.path.isfile(classifier_filepath):
        os.remove(classifier_filepath)

    wordlist_filepath = get_master_wordlist_filepath()
    if os.path.isfile(wordlist_filepath):
        os.remove(wordlist_filepath)

    with open(classifier_filepath, 'wb') as f:
        pickle.dump(classifier, f)

    with open(wordlist_filepath, 'wb') as f:
        pickle.dump(master_wordlist, f)


class SentimentClassifier:
    def __init__(self):
        self.tokenizer = SpecialTokenizer()
        self._classifier = None
        self.master_wordlist = None

        classifier_filepath = get_classifier_filepath()
        wordlist_filepath = get_master_wordlist_filepath()
        if not os.path.isfile(classifier_filepath) or not os.path.isfile(wordlist_filepath):
            main()
        with open(classifier_filepath, 'rb') as f:
            self._classifier = pickle.load(f)
        with open(wordlist_filepath, 'rb') as f:
            self.master_wordlist = pickle.load(f)


    def classify(self, tweet):
        tokens = self.tokenizer.tokenize(tweet)
        features = self.extract_features(tokens)
        probability = self._classifier.prob_classify(features)
        if probability.max() == 'positive':
            return probability.prob('positive')
        else:
            return -probability.prob('negative')

    def extract_features(self, words_list):
        words = set(words_list)
        features = {}
        for word in words:
            key = 'contains({})'.format(word)
            value = word in self._master_wordlist
            features[key] = value
        return features



if __name__ == '__main__':
    main()
