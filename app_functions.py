# Helper functions for app
import streamlit as st
import pandas as pd
import numpy as np
import gzip

from datetime import datetime
from urllib.request import urlopen

# Flow is as follows:
# 1. Download IMBD datasets (just once!)
# 2. Get all content depending on choice in order to normalise its scores
# 3. Show all or rated or unrated

# TO-DO: Compute series with combined metric

# Download latest IMDB datasets
@st.cache_data(show_spinner=False)  # Run only once (when session begins)
def unzip_and_load_datasets():

    '''
    Based on https://stackoverflow.com/questions/18146389/urlopen-trouble-while-trying-to-download-a-gzip-file
    '''

    data_urls = {
        'title_basics': 'https://datasets.imdbws.com/title.basics.tsv.gz',
        'title_ratings': 'https://datasets.imdbws.com/title.ratings.tsv.gz',
        'title_episode': 'https://datasets.imdbws.com/title.episode.tsv.gz'
    }

    datasets = []

    for key, url in data_urls.items():
        inmemory = urlopen(url)
        fStream = gzip.GzipFile(fileobj=inmemory, mode='rb')
        df = pd.read_csv(fStream, sep='\t', low_memory=False)
        datasets.append(df)
        # df.to_csv('IMDB_Data/{}.csv'.format(key))

    return datasets

# Get ratings and votes for each title
@st.cache_data(show_spinner=False)
def merge_ratings(df_imdb_titles, df_imdb_ratings):
    return df_imdb_titles.merge(df_imdb_ratings, on='tconst')   

# Get episode info
@st.cache_data(show_spinner=False)
def merge_episode_info(df_imdb_episodes, df_imdb_titles):
    return df_imdb_episodes.merge(df_imdb_titles[['tconst', 'runtimeMinutes', 'averageRating', 'numVotes']], on='tconst')

@st.cache_data(show_spinner=False)
def normalise_content(df):

    # Create score metric
    df['score'] = df['averageRating'] * df['numVotes']
    # Normalise scores in 0-10 range
    df['score'] = 10 * (df['score'] - df['score'].min()) / (df['score'].max() - df['score'].min())
    # Apply sigmoid function (out of 10)
    df['score'] = 10 / (1 + np.exp(-df['score']))
    # Score is mean of average rating and normalised metric
    df['score'] = (df['score'] + df['averageRating']) / 2
    df = df.sort_values('score', ascending=False)
    df['score'] = round(df['score'], 2)
    df.index = np.arange(1, 1+len(df))

    return df

@st.cache_data(show_spinner=False)
def calculate_episode_metric(df_imdb_episodes):

    # Group episodes by the series to which they belong and calculate their mean score
    df_episode_score = df_imdb_episodes.groupby('parentTconst').agg({'score': 'mean'})
    df_episode_score.reset_index(inplace=True)

    df_episode_score.rename(columns={'score': 'episodeScore'}, inplace=True)
    return df_episode_score

@st.cache_data(show_spinner=False)
def calculate_runtime_metric(df_imdb_episodes):

    # Fix cases with errors runtimes
    errors_list = df_imdb_episodes.loc[df_imdb_episodes['runtimeMinutes'].str.isnumeric() == False, 'runtimeMinutes'].unique()
    df_runtime_errors = df_imdb_episodes.loc[df_imdb_episodes['runtimeMinutes'].isin(errors_list)]
   
    # If series has episodes without Nan runtimes, use mean of the series (otherwise use mean of all series)
    df_runtime_without_errors = df_imdb_episodes[~df_imdb_episodes['runtimeMinutes'].isin(errors_list)].copy()
    df_runtime_without_errors['runtimeMinutes'] = df_runtime_without_errors['runtimeMinutes'].astype(int)

    # Mean of all episode lengths
    mean_runtime = df_runtime_without_errors['runtimeMinutes'].mean()

    # Mean of episode length by series
    df_mean_runtime_series = df_runtime_without_errors.groupby('parentTconst').agg({'runtimeMinutes': 'mean'})
    df_mean_runtime_series.reset_index(inplace=True)

    # 1. Use existing series info (use how='left' to keep series without runtimes for step 2)
    df_runtime_errors = df_runtime_errors.merge(df_mean_runtime_series[['parentTconst', 'runtimeMinutes']], how='left', on='parentTconst')
    df_runtime_errors.drop('runtimeMinutes_x', axis=1, inplace=True)
    df_runtime_errors.rename(columns={'runtimeMinutes_y': 'runtimeMinutes'}, inplace=True)

    # 2. If there is no info for series, runtimeMinutes columns will have become Nans -> use global mean
    df_runtime_errors.loc[df_runtime_errors['runtimeMinutes'].isna(), 'runtimeMinutes'] = mean_runtime

    # Calculate total runtime per series
    df_runtime_score = pd.concat([df_runtime_without_errors, df_runtime_errors])
    print('# EPISODES AFTER REBUILDING EPISODE RUNTIMES:', len(df_runtime_score))   # Should match value_counts in the cells above
    df_runtime_score = df_runtime_score.groupby('parentTconst').agg({'runtimeMinutes': 'sum'})
    df_runtime_score.rename(columns={'runtimeMinutes': 'totalRuntime'}, inplace=True)
    df_runtime_score['totalRuntime'] = round(df_runtime_score['totalRuntime']).astype(int)
    df_runtime_score.reset_index(inplace=True)

    return df_runtime_score

st.cache_data(show_spinner=False)
def calculate_combined_metric(df_series_score, df_episode_score, df_runtime_score):

    # Merge score with episode score
    df_combined = pd.merge(
        left=df_series_score,
        right=df_episode_score,
        left_on='tconst',
        right_on='parentTconst'
    )

    # Merge with runtime score
    df_combined = df_combined.merge(df_runtime_score, on='parentTconst')
    df_combined.drop(columns='parentTconst', inplace=True)

    df_combined = df_combined[
        [
            'tconst',
            'titleType',
            'primaryTitle',
            'originalTitle',
            'startYear',
            'endYear',
            'averageRating',
            'numVotes',
            'seriesScore',
            'episodeScore',
            'totalRuntime',
        ]
    ]

    # Using numVotes to combine with runtime score
    df_combined['combinedMetric'] = (df_combined['seriesScore'] * df_combined['episodeScore']) / 2 # Normal version
    # df_combined = normalise_scores(df_combined, score_col='combinedMetric')
    df_combined.sort_values('combinedMetric', ascending=False, inplace=True)

    return df_combined