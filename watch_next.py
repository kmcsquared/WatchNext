import streamlit as st
import numpy as np
import pandas as pd
import app_functions as af
from fetching_ratings import get_user_ratings
from datetime import datetime

# Page metadata
st.set_page_config(
    page_title='WatchNext',
    layout='wide'
)

st.title('WatchNext')

if 'loaded_data' not in st.session_state:

    with st.spinner('Downloading IMDB datasets...'):

        # Load datasets
        datasets = af.unzip_and_load_datasets()
        df_imdb_titles = datasets[0]
        df_imdb_ratings = datasets[1]
        df_imdb_episodes = datasets[2]

    with st.spinner('Merging ratings information...'):

        df_imdb_titles = pd.merge(
            left=df_imdb_titles,
            right=df_imdb_ratings,
            on='tconst'
        )
        
        df_episodes = pd.merge(
            left=df_imdb_episodes,
            right=df_imdb_titles[['tconst', 'runtimeMinutes', 'averageRating', 'numVotes']],
            on='tconst'
        )

    with st.spinner('Normalising scores...'):

        df_films = df_imdb_titles.loc[~(df_imdb_titles['titleType'].isin(['tvSeries', 'tvMiniSeries', 'tvEpisode']))]
        df_films = af.normalise_content(df_films)
        df_films.rename(columns={'score': 'filmScore'}, inplace=True)

        df_series = df_imdb_titles.loc[df_imdb_titles['titleType'].isin(['tvSeries', 'tvMiniSeries', 'tvEpisode'])]
        df_series = af.normalise_content(df_series)
        df_series.rename(columns={'score': 'seriesScore'}, inplace=True)

        df_episodes = af.normalise_content(df_episodes)             # Columns: ... / averageRating / numVotes / score
        episode_metric = af.calculate_episode_metric(df_episodes)   # Columns: parentTconst / score
        runtime_metric = af.calculate_runtime_metric(df_episodes)   # Columns: parentTconst / totalRuntime
        episode_metric.rename(columns={'score': 'episodeScore'}, inplace=True)

        df_series = pd.merge(
            left=df_series,
            right=episode_metric,
            left_on='tconst',
            right_on='parentTconst'
        )

        df_series = pd.merge(
            left=df_series,
            right=runtime_metric,
            on='parentTconst'
        )

        df_series.drop(columns='parentTconst', inplace=True)

    with st.spinner('Loading user ratings...'):
        # Load user ratings
        seen_tconst = get_user_ratings()['tconst']

    keys = ['films', 'series', 'user_ratings']
    values = [df_films, df_series, seen_tconst]

    for k, v in zip(keys, values):
        if k not in st.session_state:
            st.session_state[k] = v
    
    st.session_state['loaded_data'] = True

df_films = st.session_state['films'].copy()
df_films = df_films[
    [
        'tconst',
        'titleType',
        'primaryTitle',
        'startYear',
        'runtimeMinutes',
        'averageRating',
        'numVotes',
        'filmScore'
    ]
]

df_series = st.session_state['series'].copy()
df_series = df_series[
    [
        'tconst',
        'titleType',
        'primaryTitle',
        'startYear',
        'endYear',
        'averageRating',
        'numVotes',
        'seriesScore',
        'episodeScore',
        'totalRuntime'
    ]
]

watched_tconst = st.session_state['user_ratings'].copy()

# Films
st.header('FILMS')

show_watched_films = st.toggle(
    label='Show watched films',
    value=False
)

if not show_watched_films:
    df_films = df_films.loc[~(df_films['tconst'].isin(watched_tconst))]

df_films.index = np.arange(1, 1+len(df_films))

num_films = st.slider(
    label='Select number of films to display',
    min_value=5,
    max_value=50,
    value=5,
    step=5
)

df_films = df_films[:num_films]
st.dataframe(df_films, use_container_width=True)
af.display_covers(df_films)



# Series
st.header('SERIES')

show_watched_series = st.toggle(
    label='Show watched series',
    value=False
)

show_unfinished_series = st.toggle(
    label='Show ongoing series',
    value=False
)

if not show_watched_series:
    df_series = df_series.loc[~(df_series['tconst'].isin(watched_tconst))]

if not show_unfinished_series:
    df_series = df_series.loc[df_series['endYear'] != '\\N']
    df_series = df_series.loc[df_series['endYear'].astype(int) <= datetime.now().year]

df_series.index = np.arange(1, 1+len(df_series))

num_series = st.slider(
    label='Select number of series to display',
    min_value=5,
    max_value=50,
    value=5,
    step=5
)

df_series = df_series[:num_series]
st.dataframe(df_series, use_container_width=True)
af.display_covers(df_series, content_type='Series')