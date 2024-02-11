# Script that fetches ratings directly from IMDB
import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup

url_imdb = 'https://www.imdb.com'

# Get to page with ratings (sorted by recently added)
def get_soup(id_user):

    url_user = '{}/user/{}/ratings?sort=date_added,desc&ratingFilter=0&mode=detail&ref_=undefined&lastPosition=0'.format(url_imdb, id_user)
    r = requests.get(url_user)
    soup = BeautifulSoup(r.content, 'html.parser')

    return soup

# Find number of ratings to know whether to move onto next page and keep searching
def get_num_pages(soup):

    list_pagination = soup.find('div', {'class': 'list-pagination'})
    
    '''
    EXAMPLE
    <div class="list-pagination">
                    <a class="flat-button prev-page disabled" href="#">
                    Previous
                </a>
                <span class="pagination-range">
                    1 - 100 of 241  
                </span>
                    <a class="flat-button lister-page-next next-page" href="/user/ur103598244/ratings?sort=date_added%2Cdesc&amp;mode=detail&amp;paginationKey=mfq5ijak6z7uymjwuuwsomnsegl34knnqsdztp6xeepepyyfxdfiwpol52uhtjimq3iwclnm7gq7uk2y4kjya3yimbzdwmhr7vbxy5e47iyfrvleknv4axfhhxudjs5nyx7ijakxrvcr564pajlxuqffl4f7yiuinvqyzrwxdnv2pcuv3nats7f7dya26nspsnfs62ipenhdqflymi&amp;lastPosition=100">
                    Next
                </a>
            </div>
    '''

    # Get number of films from: 1 - 100 of 241
    num_films = list_pagination.find('span', {'class': 'pagination-range'}).text.strip()    # Get text
    num_films = num_films.split('of ')[-1]                                                  # '1 - 100 of 241' (get '241')
    num_films = int(num_films.replace(',', ''))                                             # e.g., convert '1,118' to 1118

    # Total amount of rating pages
    num_pages = 1 + (num_films // 100) # 100 shown per page
    
    return num_pages

# Switching to the next page
def get_next_page(current_num_page, soup):

    # Find next page
    list_pagination = soup.find('div', {'class': 'list-pagination'})
    next_page = list_pagination.find('a', {'class': 'flat-button lister-page-next next-page'})['href']

    # Scrape next page
    current_url = '{}{}'.format(url_imdb, next_page) 
    r = requests.get(current_url)
    soup = BeautifulSoup(r.content, 'html.parser')

    current_num_page += 1
    # print('Switching to ratings page {}: {}'.format(current_num_page, current_url))

    return current_num_page, soup

# Crawl and extract info
def extract_info(soup):

    # Dict linking ids and user ratings
    tconst_and_ratings = {}

    # List containing all content in page
    content = soup.find_all('div', {'class':'lister-item-content'})
    
    for c in content:
        content_header = c.find('h3', {'class':'lister-item-header'}).a
        # <a href="/title/tt0328832/">The Animatrix</a>
        tconst = content_header['href'].split('/')[-2]
        title = content_header.text
        user_rating = c.find('div', {'class':'ipl-rating-star ipl-rating-star--other-user small'}).find('span', {'class': 'ipl-rating-star__rating'}).text
        user_rating = int(user_rating)
        # print('TCONST: {} --- TITLE: {} --- USER RATING: {}'.format(tconst, title, user_rating))
        tconst_and_ratings[tconst] = user_rating

    return tconst_and_ratings

@st.cache_data(show_spinner=False)      # Run only once (when session begins)
def get_user_ratings(id_user='ur103598244'):

    soup = get_soup(id_user)
    current_num_page = 1
    num_pages = get_num_pages(soup)

    while current_num_page <= num_pages:
        print('Retrieving ratings from page {}/{}'.format(current_num_page, num_pages))
        # Extract info about (max) 100 pages
        # Image, title, id, year, duration, genre, date of rating, my rating, description, num votes
        if current_num_page == 1:
            tconst_and_ratings = extract_info(soup)
        else:
            tconst_and_ratings.update(extract_info(soup))
        
        print('Content retrieved:', len(tconst_and_ratings), end='\n\n')

        # Move to the next page
        if current_num_page == num_pages:
            break
        else:
            current_num_page, soup = get_next_page(current_num_page, soup)

    df_user_ratings = pd.DataFrame.from_dict(tconst_and_ratings, orient='index')
    df_user_ratings = df_user_ratings.reset_index().rename(columns={'index': 'tconst', 0: 'userRating'})

    return df_user_ratings
        


if __name__ == '__main__':
    
    tconst_and_ratings = get_user_ratings()
    print(tconst_and_ratings)