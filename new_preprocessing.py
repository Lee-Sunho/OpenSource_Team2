import re
from googleapiclient.discovery import build
import json
import pandas as pd
import torch
from transformers import ElectraForSequenceClassification, ElectraTokenizerFast

api_key = 'AIzaSyC4z-yJBlW3uNziSyQxZ7hydDm6GhxMD7U'
video_id = '9Ka1qtPAD-w'

api_obj = build('youtube', 'v3', developerKey=api_key)
response = api_obj.commentThreads().list(part="id, replies, snippet", videoId=video_id, maxResults=100).execute()

cur_index = 0
result = {}

while response:
    for item in response['items']:
        comment = item['snippet']['topLevelComment']['snippet']
        ### datatype "0" 원댓글
        result_format = {
            "datatype": "0",
            "toWho": "",
            #"cid": comment['authorChannelId']['value'],
            "author": comment['authorDisplayName'],
            "published_date": comment['publishedAt'],
            "time_num": re.sub(r'[^0-9]', '', comment['publishedAt']),
            "text": comment['textDisplay']
        }
        result[cur_index] = result_format
        cur_index = cur_index + 1

        if 'replies' in item.keys():

            reply_num = 0
            close_reference_index = 0
            close_reference = []
            reference_toWho = 0

            for reply in item['replies']['comments']:
                reply['snippet']['textDisplay'] = reply['snippet']['textDisplay'].lstrip()
                ### datatype "2" 언급대댓글
                if reply['snippet']['textDisplay'][0] == '@':
                    reference = reply['snippet']['textDisplay'].split(' ', 1)
                    reference = reference[0].replace("@", "")

                    ### 언급한 댓글 찾는 과정
                    for re_reply in item['replies']['comments']:
                        close_reference_index = close_reference_index + 1
                        if re_reply['snippet']['authorDisplayName'] == reference:
                            close_reference.append(close_reference_index)

                    if len(close_reference) == 0:
                        if reference == comment['authorDisplayName']:
                            reference_toWho = cur_index - reply_num
                    else:
                        for i in range(0, len(close_reference)):
                            close_reference[i] = abs(reply_num - close_reference[i])
                        reference_toWho = min(close_reference)

                    result_format = {
                        "datatype": "2",
                        "toWho": reference_toWho,
                        #"cid": reply['snippet']['authorChannelId']['value'],
                        "author": reply['snippet']['authorDisplayName'],
                        "published_date": reply['snippet']['publishedAt'],
                        "time_num": re.sub(r'[^0-9]', '', reply['snippet']['publishedAt']),
                        "text": reply['snippet']['textDisplay']
                    }
                    result[cur_index] = result_format
                    cur_index = cur_index + 1
                    reply_num = reply_num + 1
                ### datatype "1" 대댓글
                else:
                    result_format = {
                        "datatype": "1",
                        "toWho": cur_index - reply_num - 1,
                        #"cid": reply['snippet']['authorChannelId']['value'],
                        "author": reply['snippet']['authorDisplayName'],
                        "published_date": reply['snippet']['publishedAt'],
                        "time_num": re.sub(r'[^0-9]', '', reply['snippet']['publishedAt']),
                        "text": reply['snippet']['textDisplay']
                    }
                    result[cur_index] = result_format
                    cur_index = cur_index + 1
                    reply_num = reply_num + 1

    if 'nextPageToken' in response:
        response = api_obj.commentThreads().list(part='snippet,replies', videoId=video_id,
                                                 pageToken=response['nextPageToken'], maxResults=100).execute()
    else:
        break


### 광고도배 삭제
del_set = set()
for i in range(0, len(result)):
    curr_text = result[i]['text']
    curr_author = result[i]['author']
    for j in range(i+1, len(result)):
        target_text = result[j]['text']
        target_author = result[j]['author']
        if curr_text == target_text and curr_author == target_author:
            del_set.add(i)      # i와
            del_set.add(j)      # j set에 삽입

for i in del_set:
    result.pop(i)


### 시간순 정렬
result = sorted(result.items(), key=lambda x: x[1]['time_num'], reverse=True)
result = dict(result)


### 정렬 후 순서대로 index 번호 리스트에 넣어놓고 리스트 순서(메꾼 후 real index)랑 매치해서 toWho 수정
real_index = []
compare_index = 0
for i in result:
    real_index.append([i, compare_index])
    compare_index = compare_index + 1


# ### 삭제된 index 메꾸기
# final_result = {}
# j = 0
# for i in result:
#     final_result[j] = result[i]
#     j = j + 1


# 여기 문제! "124번을 가르쳐야 하는데 253을 가르침, 253이 아니어야 하는 얘도 253임 ex. 무야호(파프리카로 닉변함)"
# index num 수정
# j[0] = 6, 7, 8, 9, 10, ~
# j[1] = 0, 1, 2, 3, 4, ~
# for i in final_result:
#     for j in range(0, len(real_index)):
#         if real_index[j][0] == final_result[i]['toWho']:
#             print("j[0], j[1]: ", real_index[j][0], real_index[j][1])
#             final_result[i]['toWho'] = real_index[j][1]
#             print("final_result: ", final_result[i]['toWho'])


######################## 감성분석 ##########################

args = {
    'train_data_path': './ratings_train.txt',
    'val_data_path': './ratings_test.txt',
    'save_path': './model',
    'max_epochs': 1,
    'model_path': 'beomi/KcELECTRA-base',
    'batch_size': 32,
    'learning_rate': 5e-5,
    'warmup_ratio': 0.0,
    'max_seq_len': 128
}

model = ElectraForSequenceClassification.from_pretrained(args['save_path'])
tokenizer = ElectraTokenizerFast.from_pretrained(args['model_path'])

### 한 줄씩 감성 분석
for i in result:
    try:
        input_vector = tokenizer.encode(result[i]['text'], return_tensors='pt')
        pred = model(input_ids=input_vector, labels=None).logits.argmax(dim=-1).tolist()
    except:
        continue
    result[i]['score'] = pred[0]

with open('final.json', 'w', encoding='utf-8') as make_file:
    json.dump(result, make_file, ensure_ascii=False, indent='\t')