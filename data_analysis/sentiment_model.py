import os
import re
import random
import pickle

import nltk
from nltk.corpus.util import LazyCorpusLoader
from nltk.corpus import TwitterCorpusReader
from nltk.tokenize.casual import TweetTokenizer
from nltk.classify import NaiveBayesClassifier
from nltk.stem import SnowballStemmer


class SentimentClassifier:
    def __init__(self):
        self.tokenizer = CustomTokenizer()
        self._classifier = None
        self._master_wordlist = None
        classifier_filepath = get_classifier_filepath()
        wordlist_filepath = get_master_wordlist_filepath()
        if not os.path.isfile(classifier_filepath) or not os.path.isfile(wordlist_filepath):
            main()
        with open(classifier_filepath, 'rb') as f:
            self._classifier = pickle.load(f)
        with open(wordlist_filepath, 'rb') as f:
            self._master_wordlist = pickle.load(f)

    def extract_features(self, words_list):
        words = set(words_list)
        features = {}
        for word in words:
            key = 'contains({})'.format(word)
            value = word in self._master_wordlist
            features[key] = value
        return features

    def classify(self, tweet):
        tokens = self.tokenizer.tokenize(tweet)
        features = self.extract_features(tokens)
        probability = self._classifier.prob_classify(features)

        if probability.max() == 'positive':
            return 1
        else:
            return -1

 
class CustomTokenizer(TweetTokenizer):
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
        self._stemmer = SnowballStemmer('english')

        # https://github.com/nltk/nltk/blob/develop/nltk/tokenize/casual.py#L327
        self.twitter_handle_re = re.compile(r"(?<![A-Za-z0-9_!@#\$%&*])@(([A-Za-z0-9_]){20}(?!@))|(?<![A-Za-z0-9_!@#\$%&*])@(([A-Za-z0-9_]){1,19})(?![A-Za-z0-9_]*@)")

        # https://gist.github.com/uogbuji/705383
        self.url_re = re.compile(r'(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'".,<>?\xab\xbb\u201c\u201d\u2018\u2019]))')

    def fix_handles(self, text):
        return self.twitter_handle_re.sub('__handle', text)

    def handle_urls(self, text):
        return self.url_re.sub('__url', text)

    def stem(self, words):
        return [self._stemmer.stem(word) for word in words if not word in string.punctuation]

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

def make_classifier():
    positive_file = 'positive_tweets.json'
    negative_file = 'negative_tweets.json'
    files = [positive_file, negative_file]

    twitter_samples = LazyCorpusLoader('twitter_samples',
                                       TwitterCorpusReader,
                                       files,
                                       word_tokenizer=CustomTokenizer())

    # this returns a list of lists
    twitter_tokens = twitter_samples.tokenized()

    # need to unpack our list of lists, using a nested list comprehension
    frequency_dist = nltk.FreqDist(x for sub in twitter_tokens for x in sub)
    frequency_dist.pprint(100)
    master_list_of_words = tuple(frequency_dist.keys())
    extraction_function = make_extract_features_func(master_list_of_words)

    positive_tokens = twitter_samples.tokenized(positive_file)
    negative_tokens = twitter_samples.tokenized(negative_file)

    positive_tokens = [(token, 'positive') for token in positive_tokens]
    negative_tokens = [(token, 'negative') for token in negative_tokens]

    all_tokens = positive_tokens + negative_tokens
    random.shuffle(all_tokens)

    training_set = nltk.classify.apply_features(extraction_function,
                                                all_tokens)

    classifier = NaiveBayesClassifier.train(training_set)

    return classifier, master_list_of_words


def make_extract_features_func(master_list_of_words):
    def extraction_func(word_list):
        words = set(word_list)
        result = {}
        for word in words:
            result_key = 'contains({})'.format(word)
            result_value = word in master_list_of_words
            result[result_key] = result_value

        return result

    return extraction_func

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

if __name__ == '__main__':
    main()
