from ddtrace import tracer
from transformers import pipeline
import torch

# 1. Initialize once (Global scope) to avoid reloading heavy weights
# device=-1 runs on CPU. Set to 0 if you have a GPU.

device = "mps" if torch.backends.mps.is_available() else "cpu"

msg_classifier = pipeline("zero-shot-classification", 
                      model="facebook/bart-large-mnli",
                      device=device) 

CANDIDATE_LABELS = [
    "Order Status", 
    "Return & Refund", 
    "Product Info", 
    "Billing & Account", 
    "Shipping Policy", 
    "Technical Support", 
    "Other"
]

emotion_pipeline = pipeline("text-classification", 
                        model="SamLowe/roberta-base-go_emotions", 
                        top_k=None,
                        device=device)

sentiment_pipeline = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english", device=device  )



async def tag_message(query, parent_context, confusion_score):
    # REACTIVATE the parent trace so this span appears in the same flame graph
    tracer.context_provider.activate(parent_context)
    
    with tracer.trace("background.topic_classification") as span:

        result = msg_classifier(query, CANDIDATE_LABELS)

        top_topic = result['labels'][0]
        #confidence = result['scores'][0]
        
        # Tag the span for analysis
        span.set_tags({"user.topic": top_topic, "user.confusion_score": float(confusion_score)})     
        # Emit a metric for dashboards
        print(f"Background task finished. Topic: {top_topic}")

async def get_confusion_score(text, parent_context):
    # Run inference
    tracer.context_provider.activate(parent_context)
    
    with tracer.trace("background.confusion_score") as span:

        results = emotion_pipeline(text) # Returns list of lists [[{'label': 'confusion', 'score': 0.9}, ...]]
        
        # Extract just the 'confusion' score
        # The output is a list of dicts; we find the one where label='confusion'
        confusion_score = next(item['score'] for item in results[0] if item['label'] == 'confusion')

        span.set_metric("user.confusion_score", float(confusion_score))
        return confusion_score

async def set_emotion(text, parent_context):
    tracer.context_provider.activate(parent_context)
    
    with tracer.trace("background.emotion_classification") as span:
        result = sentiment_pipeline(text)
        emotion = result[0]['label']
        span.set_tag("user.emotion", emotion)


async def set_emotion_tags(text, parent_context):
    await set_emotion(text, parent_context)
    confusion_score = await get_confusion_score(text, parent_context)
    await tag_message(text, parent_context, confusion_score)