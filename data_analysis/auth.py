from tweepy import OAuthHandler


consumer_key = 'dGx62GNqi7Yaj1XIcZgOLNjDb'
consumer_secret = 'ZCE896So7Ba1u96ICwMhulO2QO3oeZ5BeVyfUw1YbIYELzVyJs'
access_token = '1121993185-hGOTr3J40FlKGwWkiNWdeNVrcD4bqqW38SPiM3s'
access_token_secret = 'BAo4d2J24xyXRKFrga6A9MwpTW6bMb5EztfvnL5qv2LvJ'

auth = OAuthHandler(consumer_key,
                    consumer_secret)

auth.set_access_token(access_token, access_token_secret)
