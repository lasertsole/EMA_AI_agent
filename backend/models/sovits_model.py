import requests
from pydantic import BaseModel

"""
### 推理请求参数
{
    "text": "",                   # str.(required) text to be synthesized
    "text_lang: "",               # str.(required) language of the text to be synthesized
    "ref_audio_path": "",         # str.(required) reference audio path
    "aux_ref_audio_paths": [],    # list.(optional) auxiliary reference audio paths for multi-speaker tone fusion
    "prompt_text": "",            # str.(optional) prompt text for the reference audio
    "prompt_lang": "",            # str.(required) language of the prompt text for the reference audio
    "top_k": 15,                  # int. top k sampling
    "top_p": 1,                   # float. top p sampling
    "temperature": 1,             # float. temperature for sampling
    "text_split_method": "cut5",  # str. text split method, see text_segmentation_method.py for details.
    "batch_size": 1,              # int. batch size for inference
    "batch_threshold": 0.75,      # float. threshold for batch splitting.
    "split_bucket": True,         # bool. whether to split the batch into multiple buckets.
    "speed_factor":1.0,           # float. control the speed of the synthesized audio.
    "fragment_interval":0.3,      # float. to control the interval of the audio fragment.
    "seed": -1,                   # int. random seed for reproducibility.
    "parallel_infer": True,       # bool. whether to use parallel inference.
    "repetition_penalty": 1.35,   # float. repetition penalty for T2S model.
    "sample_steps": 32,           # int. number of sampling steps for VITS model V3.
    "super_sampling": False,      # bool. whether to use super-sampling for audio when using VITS model V3.
    "streaming_mode": False,      # bool or int. return audio chunk by chunk.T he available options are: 0,1,2,3 or True/False (0/False: Disabled | 1/True: Best Quality, Slowest response speed (old version streaming_mode) | 2: Medium Quality, Slow response speed | 3: Lower Quality, Faster response speed )
    "overlap_length": 2,          # int. overlap length of semantic tokens for streaming mode.
    "min_chunk_length": 16,       # int. The minimum chunk length of semantic tokens for streaming mode. (affects audio chunk size)
}
"""
class TTS_Request(BaseModel):
    text: str = None
    text_lang: str = None
    ref_audio_path: str = None
    aux_ref_audio_paths: list = None
    prompt_lang: str = None
    prompt_text: str = ""
    top_k: int = 15
    top_p: float = 1
    temperature: float = 1
    text_split_method: str = "cut5"
    batch_size: int = 1
    batch_threshold: float = 0.75
    split_bucket: bool = True
    speed_factor: float = 1.0
    fragment_interval: float = 0.3
    seed: int = -1
    media_type: str = "wav"
    streaming_mode: Union[bool, int] = False
    parallel_infer: bool = True
    repetition_penalty: float = 1.35
    sample_steps: int = 32
    super_sampling: bool = False
    overlap_length: int = 2
    min_chunk_length: int = 16

base_url = "http://127.0.0.1:9880/"
control_url = base_url + "/control"
tts_url = base_url + "/tts"
change_GPT_url = base_url + "/set_gpt_weights"
change_sovits_url = base_url + "/set_sovits_weights"
change_refer_audio_url = base_url + "/set_refer_audio"

### 推理
def fetchTTSSound(request: TTS_Request):
    res = requests.post(tts_url, data=json.dumps(data), verify=True)
    print(res)
    return res
    
```
### 命令控制

command:
"restart": 重新运行
"exit": 结束运行
```
def controlModel(command: str = None):
    if(command is None || (command != "restart" && (command != "exit"))
        return
    payload={
        command: weights_path
    }
    
    res = requests.get(control_url, params=payload)
    print(res)
    return res

### 切换GPT模型
def changeGPTModel(weights_path: str = None):
    if(weights_path is None)
        return

    payload={
        weights_path: weights_path
    }
    
    res = requests.get(change_GPT_url, params=payload)
    print(res)
    return res

### 切换Sovits模型
def changeSovitsModel(weights_path: str = None):
    if(weights_path is None)
        return

    payload={
        weights_path: weights_path
    }
    
    res = requests.get(change_sovits_url, params=payload)
    print(res)
    return res
    
### 切换参考音频
def changeReferAudio(refer_audio_path: str = None):
    if(weights_path is None)
        return

    payload={
        refer_audio_path: refer_audio_path
    }
    
    res = requests.get(change_refer_audio_url, params=payload)
    print(res)
    return res
