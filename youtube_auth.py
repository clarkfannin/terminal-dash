#!/usr/bin/env python3

# Generates token on first auth

import os
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/youtube.readonly',
    'https://www.googleapis.com/auth/yt-analytics.readonly'
]

def authenticate():
    creds = None
    
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError("credentials.json not found")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    youtube = build('youtube', 'v3', credentials=creds)
    youtube_analytics = build('youtubeAnalytics', 'v2', credentials=creds)
    
    return youtube, youtube_analytics

def get_youtube_stats():
    youtube, youtube_analytics = authenticate()
    
    channel_response = youtube.channels().list(
        part='statistics',
        mine=True
    ).execute()
    
    if not channel_response.get('items'):
        raise Exception("No channel found")
    
    channel_stats = channel_response['items'][0]['statistics']
    channel_id = channel_response['items'][0]['id']
    
    uploads_response = youtube.search().list(
        part='id',
        forMine=True,
        type='video',
        order='date',
        maxResults=3
    ).execute()
    
    last_3_video_ids = [item['id']['videoId'] for item in uploads_response.get('items', [])]
    
    last_3_views = []
    last_3_titles = []
    if last_3_video_ids:
        video_stats = youtube.videos().list(
            part='statistics,snippet',
            id=','.join(last_3_video_ids)
        ).execute()
        
        last_3_views = [
            int(item['statistics'].get('viewCount', 0)) 
            for item in video_stats.get('items', [])
        ]
        last_3_titles = [
            item['snippet'].get('title', 'Unknown') 
            for item in video_stats.get('items', [])
        ]
    
    while len(last_3_views) < 3:
        last_3_views.append(0)
    while len(last_3_titles) < 3:
        last_3_titles.append('No video')
    
    end_date = (datetime.now() - timedelta(days=1)).date()
    start_date = end_date - timedelta(days=7)
    
    top_video_response = youtube_analytics.reports().query(
        ids=f'channel=={channel_id}',
        startDate=start_date.isoformat(),
        endDate=end_date.isoformat(),
        metrics='views',
        dimensions='video',
        sort='-views',
        maxResults=1
    ).execute()
    
    top_video_views = 0
    if top_video_response.get('rows'):
        top_video_views = int(top_video_response['rows'][0][1])
    
    return {
        'last_3_videos_views': last_3_views,
        'last_3_videos_titles': last_3_titles,
        'top_video_views': top_video_views,
        'subscribers': int(channel_stats.get('subscriberCount', 0)),
        'total_videos': int(channel_stats.get('videoCount', 0))
    }

def main():
    """Example usage"""
    try:
        stats = get_youtube_stats()
        
        print("YouTube Channel Stats:")
        print(f"  Last 3 Videos Views: {stats['last_3_videos_views']}")
        print(f"  Last 3 Videos Titles: {stats['last_3_videos_titles']}")
        print(f"  Top Video Views (7d): {stats['top_video_views']}")
        print(f"  Subscribers: {stats['subscribers']}")
        print(f"  Total Videos: {stats['total_videos']}")
        
        return stats
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    main()