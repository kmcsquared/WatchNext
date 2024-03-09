# Helper functions for app
import streamlit as st
import pandas as pd
import numpy as np
import gzip

from datetime import datetime
from urllib.request import urlopen

import requests
from imdb import Cinemagoer
from PIL import Image
from io import BytesIO

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
        print('Loaded {}'.format(key))
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
def normalise_content(df, content_type):

    # Remove outlier ratings
    if content_type in ['Series', 'Films']:
        df = df.loc[df['numVotes'] >= 5000].copy()

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
    df_episode_score['score'] = round(df_episode_score['score'], 2)
    df_episode_score.reset_index(inplace=True)

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

@st.cache_data(show_spinner=False)
def display_covers(df_content, content_type=None):

    # Display content
    cg = Cinemagoer()   # Get access to IMDB API for retrieving photos
    n_cols = 5

    for idx, tconst in enumerate(df_content['tconst']):
        # Fetch image if not retrieved already
        if tconst not in st.session_state:
            content = cg.get_movie(tconst[2:])

            # TO-DO: Get image link from the web scraping
            # Read and resize image: https://stackoverflow.com/questions/7391945/how-do-i-read-image-data-from-a-url-in-python
            img_data = requests.get(content['full-size cover url']).content
            content_image = Image.open(BytesIO(img_data)).resize((1200,1800))
            
            # Save variables obtained through requests in cache
            st.session_state['image_{}'.format(tconst)] = content_image
            
            tconst_info = df_content.loc[df_content['tconst'] == tconst].values[0]
            primary_title = tconst_info[2]
            start_year = tconst_info[3]
            score = tconst_info[7]
            
            if content_type == 'Series':
                end_year = tconst_info[4]
                if end_year == '\\N':
                    end_year = ''
            
            content_caption = '{}. {} ({:.2f}) --- ({}{})'.format(
                idx+1, 
                primary_title,
                score,
                start_year,
                '-{}'.format(end_year) if content_type == 'Series' else ''
            )

            # Store caption (everything except idx)
            st.session_state['caption_{}'.format(tconst)] = ''.join(content_caption.split(sep='. ', maxsplit=1)[-1])

            # Mark tconst as seen after image and caption have been stored
            st.session_state[tconst] = True

        # Add a new row when end of row is reached
        if idx % n_cols == 0:
            cols = st.columns(n_cols)

        cols[idx % n_cols].image(
            image=st.session_state['image_{}'.format(tconst)], 
            caption='{}. {}'.format(
                idx+1, 
                st.session_state['caption_{}'.format(tconst)]
            )
        )

    st.divider()


@st.cache_data(show_spinner=False)
def display_covers_connections(df_content):

    # Display content
    cg = Cinemagoer()   # Get access to IMDB API for retrieving photos
    n_cols = 5

    # TO-DO: If title whose connections is being searched has not been watched, display it too.

    # Titles which are not connections are null, iterate through them
    # and show images of connection iteratively
    nan_indices = df_content.index[df_content['connection'].isna()].tolist()
    nan_ranges = zip(nan_indices, nan_indices[1:])
    
    for idxA, idxB in nan_ranges:
        original_title = df_content.iloc[idxA]['primaryTitle']
        original_tconst = df_content.iloc[idxA]['tconst']

        st.subheader('{} ({})'.format(original_title, original_tconst))

        # If unseen single title
        if idxB-idxA == 1:
            connection_tconsts = [df_content.loc[idxA, 'tconst']]
        else:
            connection_tconsts = df_content.loc[idxA+1:idxB-1, 'tconst']

        for idx, tconst in enumerate(connection_tconsts):
            # Fetch image if not retrieved already
            if tconst not in st.session_state:
                content = cg.get_movie(tconst[2:])

                # Read and resize image: https://stackoverflow.com/questions/7391945/how-do-i-read-image-data-from-a-url-in-python
                img_data = requests.get(content['full-size cover url']).content
                content_image = Image.open(BytesIO(img_data)).resize((1200,1800))
                
                # Save variables obtained through requests in cache
                st.session_state['image_{}'.format(tconst)] = content_image
                
                tconst_info = df_content.loc[df_content['tconst'] == tconst].values[0]
                primary_title = tconst_info[1]
                title_type = tconst_info[3]
                
                content_caption = '{}. {} ({})'.format(
                    idx+1, 
                    primary_title,
                    title_type
                )

                # Store caption (everything except idx)
                st.session_state['caption_{}'.format(tconst)] = ''.join(content_caption.split(sep='. ', maxsplit=1)[-1])

                # Mark tconst as seen after image and caption have been stored
                st.session_state[tconst] = True

            # Add a new row when end of row is reached
            if idx % n_cols == 0:
                cols = st.columns(n_cols)

            cols[idx % n_cols].image(
                image=st.session_state['image_{}'.format(tconst)], 
                caption='{}. {}'.format(
                    idx+1, 
                    st.session_state['caption_{}'.format(tconst)]
                )
            )

    st.divider()


def get_new_episodes(titles, episodes, df_user_ratings):

    '''
    Use year of user ratings to look for episodes released after that year
    '''

    # Only keep episodes of watched series
    episodes_of_watched_series = episodes.loc[episodes['parentTconst'].isin(df_user_ratings['tconst'])].copy()
    # Get primaryTitle of series
    episodes_of_watched_series = pd.merge(episodes_of_watched_series, titles[['tconst', 'primaryTitle']], left_on='parentTconst', right_on='tconst')
    episodes_of_watched_series.rename(columns={'primaryTitle': 'parentTitle', 'tconst_x': 'tconst'}, inplace=True)
    episodes_of_watched_series.drop(columns='tconst_y', inplace=True)

    # Get episode name
    episodes_of_watched_series = pd.merge(episodes_of_watched_series, titles[['tconst', 'primaryTitle']], on='tconst')

    # Find unaired pilots, special episodes...
    unexpected_numbers = [-1,0]
    unexpected_episodes = episodes_of_watched_series.loc[(episodes_of_watched_series['seasonNumber'].isin(unexpected_numbers)) | (episodes_of_watched_series['episodeNumber'].isin(unexpected_numbers))].copy()
    unexpected_episodes.reset_index(inplace=True)

    # Get year of episode
    episodes_of_watched_series = pd.merge(
        left=episodes_of_watched_series,
        right=titles[['tconst', 'startYear']],
        on='tconst'
    )

    # Some unreleased episodes will show as '\\N', so convert them to -1
    episodes_of_watched_series.loc[~(episodes_of_watched_series['startYear'].str.isnumeric()), 'startYear'] = -1

    # Merge with user ratings
    episodes_of_watched_series = pd.merge(
        left=episodes_of_watched_series,
        right=df_user_ratings[['tconst', 'dateRating']],
        left_on='parentTconst',
        right_on='tconst'
    )

    episodes_of_watched_series.rename(columns={'tconst_x': 'tconst'}, inplace=True)
    episodes_of_watched_series.drop(columns='tconst_y', inplace=True)

    episodes_of_watched_series['startYear'] = episodes_of_watched_series['startYear'].astype(int)
    episodes_of_watched_series['newEpisode'] = episodes_of_watched_series['startYear'] > episodes_of_watched_series['dateRating']

    # Sort by series, season and episode number
    for col in ['seasonNumber', 'episodeNumber']:
        episodes_of_watched_series.loc[episodes_of_watched_series[col] == '\\N', col] = -1

    episodes_of_watched_series['seasonNumber'] = episodes_of_watched_series['seasonNumber'].astype(int)
    episodes_of_watched_series['episodeNumber'] = episodes_of_watched_series['episodeNumber'].astype(int)

    episodes_of_watched_series.sort_values(['parentTconst', 'seasonNumber', 'episodeNumber'], inplace=True)
    
    unwatched_episodes = episodes_of_watched_series.loc[episodes_of_watched_series['newEpisode']]
    unwatched_episodes.reset_index(inplace=True)

    return unwatched_episodes, unexpected_episodes


@st.cache_data(show_spinner=False)
def display_covers_unwatched_episodes(df_new_episodes):

    # Display content
    cg = Cinemagoer()   # Get access to IMDB API for retrieving photos
    n_cols = 5

    for parent_tconst in df_new_episodes['parentTconst'].unique():
        
        df_content = df_new_episodes.loc[df_new_episodes['parentTconst'] == parent_tconst].copy()
        parent_title = df_content['parentTitle'].values[0]
        st.subheader('{} ({})'.format(parent_title, parent_tconst))

        for idx, tconst in enumerate(df_content['tconst']):
            # Fetch image if not retrieved already
            if tconst not in st.session_state:
                content = cg.get_movie(tconst[2:])

                # TO-DO: Get image link from the web scraping
                # Read and resize image: https://stackoverflow.com/questions/7391945/how-do-i-read-image-data-from-a-url-in-python
                img_data = requests.get(content['full-size cover url']).content
                content_image = Image.open(BytesIO(img_data)).resize((1200,1200))
                
                # Save variables obtained through requests in cache
                st.session_state['image_{}'.format(tconst)] = content_image
                
                tconst_info = df_content.loc[df_content['tconst'] == tconst].iloc[0]
                num_season = tconst_info['seasonNumber']
                num_episode = tconst_info['episodeNumber']
                episode_title = tconst_info['primaryTitle']
                
                content_caption = 'S{}E{} - {}'.format(
                    num_season, 
                    num_episode,
                    episode_title
                )

                # Store caption (everything except idx)
                st.session_state['caption_{}'.format(tconst)] = content_caption

                # Mark tconst as seen after image and caption have been stored
                st.session_state[tconst] = True

            # Add a new row when end of row is reached
            if idx % n_cols == 0:
                cols = st.columns(n_cols)

            cols[idx % n_cols].image(
                image=st.session_state['image_{}'.format(tconst)], 
                caption=st.session_state['caption_{}'.format(tconst)]
            )

    st.divider()