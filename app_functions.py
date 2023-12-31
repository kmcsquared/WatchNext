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
# @st.cache_data(show_spinner=False)    # Run only once (when session begins)
def unzip_and_load_datasets():

    '''
    Based on https://stackoverflow.com/questions/18146389/urlopen-trouble-while-trying-to-download-a-gzip-file
    '''

    titles_zip_url = 'https://datasets.imdbws.com/title.basics.tsv.gz'
    episodes_zip_url = 'https://datasets.imdbws.com/title.episode.tsv.gz'
    ratings_zip_url = 'https://datasets.imdbws.com/title.ratings.tsv.gz'

    datasets = []

    for url in [titles_zip_url, episodes_zip_url, ratings_zip_url]:
        inmemory = urlopen(url)
        fStream = gzip.GzipFile(fileobj=inmemory, mode='rb')
        datasets.append(pd.read_csv(fStream, sep='\t'))

    return datasets

# Loading all content is needed once per content type
# to allow to normalise with respect to all titles
@st.cache_data(show_spinner=False)
def load_content_type(content_choice, titles):

    # Get content by type
    if content_choice == 'Non Series':
        return titles[~titles['titleType'].isin(['tvSeries', 'tvMiniSeries', 'tvEpisode', 'videoGame'])]
    elif content_choice == 'Series':
        return titles[titles['titleType'].isin(['tvSeries', 'tvMiniSeries'])]
    elif content_choice == 'Videogames':
        return titles[titles['titleType'].isin(['videoGame'])]


# Compute normalisation of scores
@st.cache_data(show_spinner=False)
def normalise_scores(df_score):

    # Normalise scores in 0-10 range
    normalised_metric = 10 * (df_score['score'] - df_score['score'].min()) / (df_score['score'].max() - df_score['score'].min())
        # Apply sigmoid function (out of 10)
    normalised_metric = 10 / (1 + np.exp(-normalised_metric))
        
    # Score is mean of average rating and normalised metric
    df_score['score'] = (df_score['averageRating'] + normalised_metric) / 2
    df_score = df_score.sort_values('score', ascending=False)
    df_score['score'] = round(df_score['score'], 2)

    # Discard those with averageRating == 10 (outliers)
    scores_10 = df_score[df_score['averageRating'] == 10]
    if len(scores_10) != 0:
        index_first_10 = scores_10.index[0]
        votes_first_10 = df_score.loc[index_first_10, 'numVotes']
        df_score = df_score[df_score['numVotes'] > votes_first_10]

    # df_score.index = np.arange(1, 1+len(df_score))

    return df_score
  
# Add scores to dataset
@st.cache_data(show_spinner=False)
def compute_scores(df_content, ratings):

    # Merge ratings
    df_content = df_content.merge(ratings, on='tconst')

    # Create score column
    df_content['score'] = df_content['averageRating'] * df_content['numVotes']
    # Sort by score
    df_content = df_content.sort_values('score', ascending=False)

    df_content = normalise_scores(df_content)
    return df_content


    
# Selecting content choice
def select_content_by_show_choice(df_content, show_choice, df_user_ratings):

    '''
    df_content: DataFrame containing normalised scores
    show_choice: one of (All, Rated, Unrated)
    '''

    if show_choice == 'All':
        return df_content
    
    if show_choice == 'Rated':
        return df_content.merge(df_user_ratings, on='tconst')
        
    if show_choice == 'Unrated':
        return df_content[~df_content['tconst'].isin(df_user_ratings['tconst'])]


# Show only finished series
def show_finished_series(df_score):

    # Remove unfinished series
    finished_series = df_score[df_score['endYear'] != '\\N']
    # Remove series that end after current year
    current_year = datetime.now().year
    finished_series = finished_series[finished_series['endYear'].astype(int) <= current_year]

    return finished_series