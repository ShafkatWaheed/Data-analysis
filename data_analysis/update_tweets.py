from math import floor
from tweepy import API, OAuthHandler

from data_analysis.database import session, Tweet

consumer_key = 'dGx62GNqi7Yaj1XIcZgOLNjDb'
consumer_secret = 'ZCE896So7Ba1u96ICwMhulO2QO3oeZ5BeVyfUw1YbIYELzVyJs'
access_token = '1121993185-hGOTr3J40FlKGwWkiNWdeNVrcD4bqqW38SPiM3s'
access_token_secret = 'BAo4d2J24xyXRKFrga6A9MwpTW6bMb5EztfvnL5qv2LvJ'

auth = OAuthHandler(consumer_key,
                    consumer_secret)

auth.set_access_token(access_token, access_token_secret)


def update_tweets(api, tweets):
    """
    This is a method to update our tweets. 
    `api` is an instance of tweepy.API
    `tweets` is a list of all tweets from our database

    This method handles high level iteration logic. See `_update_sets` for the
    more interesting, updating-of-values, logic
    """
    # How many tweets do we have?
    len_tweets = len(tweets)
    # The Twitter REST API only takes 100 id's at a time. So we need to break
    # these into sets of 100, and use the `math.floor` method to get an integer
    iterations = floor(len_tweets/100)
   
    # Iterate through the sets of 100s of tweets
    for num in range(iterations):
        # first number of the set of 100
        first_tweet_index = num * 100
        # last number of the set of 100 
        last_tweet_index = first_tweet_index + 99
        # Grab the set using index slicing
        tweet_set = tweets[first_tweet_index:last_tweet_index]

        # Call an the inner method so we avoid code duplication
        _update_sets(api, session, tweet_set, num)

    # if we can divide perfectly by 100, we're done!
    if iterations % 100 == 0:
        return

    # If we're here, our last set is slightly smaller than 100, so we're 
    # going to caculate the next number and then grab to the end of the list
    last_set_num = iterations * 100
    last_set = tweets[last_set_num:]
    # pass the last set into our inner method that we used to avoid code
    # duplication
    _update_sets(api, session, last_set, iterations)


def _update_sets(api, session, tweet_set, start_num):
    """
    Broke out a helper method so we didn't have to repeat the code for our
    last set.

    This helper method does the heavy lifting for us
    """
    # Grab out just the tweet ids using a list comprehension
    tweet_ids = [tweet.tid for tweet in tweet_set]
    # Using the tweepy api, grab the updated tweets
    # `trim_user` drops user data
    updated_set = api.statuses_lookup(tweet_ids, trim_user=True)

    # iterate through update set
    for updated_tweet in updated_set:
        # the values we want to update
        fav_count = updated_tweet.favorite_count
        retweet_count = updated_tweet.retweet_count

        # Get the old tweet using it's twitter id (tid for short)
        tid = updated_tweet.id
        database_tweet = session.query(Tweet).filter_by(tid=tid).one()

        # update the tweet information in our database
        database_tweet.favorite_count = fav_count
        database_tweet.retweet_count = retweet_count

        # User feedback
        print('index: {}'.format(database_tweet.id))
        print('favs: {} \t retweets: {}'.format(fav_count, retweet_count))

    # save our changes to the database
    session.commit()


def main():
    api = API(auth)
    # Grab all the tweets
    tweets = session.query(Tweet).all()
    update_tweets(api, tweets)


if __name__ == '__main__':
    main()
