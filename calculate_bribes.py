#!/usr/bin/env python

import sys

import requests
from dateutil.parser import parse
from tabulate import tabulate

my_aqua = int(sys.argv[1]) * 1000
stats_url = 'https://voting-tracker.aqua.network/api/voting-snapshot/stats/'
bribes_url = 'https://bribes-api.aqua.network/api/bribes/?limit=20&page=1'
votes_url = 'https://voting-tracker.aqua.network/api/voting-snapshot/'
market_keys_url = 'https://marketkeys-tracker.aqua.network/api/market-keys/'

stats_data = requests.get(stats_url)
total_voted = float(stats_data.json()['adjusted_votes_value_sum'])

bribes_data = requests.get(bribes_url)

bribes = {}
for bribe in bribes_data.json()['results']:
    bribes[bribe['market_key']] = {
        'daily_amount_aqua': sum(float(b['daily_aqua_equivalent']) for b in bribe['aggregated_bribes']),
        'stop_at': min(parse(b['stop_at']) for b in bribe['aggregated_bribes'])
    }
    distribution = []
    for ab in bribe['aggregated_bribes']:
        distribution.append((
            ab['asset_code'],
            '{:.2f}'.format(float(ab['daily_aqua_equivalent']) / bribes[bribe['market_key']]['daily_amount_aqua'])
        ))

    distribution = list(reversed(sorted(distribution, key=lambda d: d[1])))
    bribes[bribe['market_key']]['distribution'] = distribution
    if len(distribution) == 1:
        distribution_text = distribution[0][0]
    else:
        distribution_text = ', '.join(['{}: {}'.format(*d) for d in distribution])
    bribes[bribe['market_key']]['distribution_text'] = distribution_text

votes_data = requests.get(votes_url + '?' + '&'.join(f'market_key={key}' for key in bribes.keys()))
for vote in votes_data.json()['results']:
    vote_value = float(vote['votes_value'])
    bribes[vote['market_key']]['votes'] = vote_value
    bribes[vote['market_key']]['percentage'] = vote_value / total_voted
    bribes[vote['market_key']]['total_percentage'] = (vote_value + my_aqua) / (total_voted + my_aqua)

# filter out pairs with no votes
bribes = {
    key: bribe
    for key, bribe in bribes.items()
    if bribe.get('percentage')
}

# get pair
keys_data = requests.get(market_keys_url + '?' + '&'.join(f'account_id={key}' for key in bribes.keys()))
for key in keys_data.json()['results']:
    bribes[key['account_id']]['pair'] = '{} / {}'.format(key['asset1_code'], key['asset2_code'])

# calculate boosts
for bribe in bribes.values():
    if 'AQUA' not in bribe['pair']:
        continue
    bribe['percentage'] *= 1.5
    bribe['total_percentage'] *= 1.5

for bribe in bribes.values():
    bribe['my_value'] = my_aqua / (bribe['votes'] + my_aqua) * bribe['daily_amount_aqua']
    bribe['my_share'] = my_aqua / bribe['votes']

# filter out unavailable pairs
bribes = {
    key: bribe
    for key, bribe in bribes.items()
    if bribe.get('votes')
}

# filter out of reward zone
bribes = {
    key: bribe
    for key, bribe in bribes.items()
    if bribe['total_percentage'] > 0.01
}

top_bribes = reversed(sorted(bribes.values(), key=lambda b: b['my_value']))
result_table = []
for bribe in top_bribes:
    result_table.append([
        bribe['pair'], int(bribe['my_value']), bribe['my_share'] * 100,
        '{:.2f} -> {:.2f}'.format(bribe['percentage'] * 100, bribe['total_percentage'] * 100),
        bribe['stop_at'].strftime('%Y-%m-%d'),
        bribe['distribution_text']
    ])

print(
    tabulate(
        result_table,
        headers=['Pair', 'Profit (AQUA)', 'My share %', '% of votes', 'Stop at', 'Paid in'],
        floatfmt=".2f"
    )
)
