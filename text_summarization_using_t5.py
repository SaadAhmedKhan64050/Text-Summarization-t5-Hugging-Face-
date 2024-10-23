# -*- coding: utf-8 -*-
"""Text Summarization using T5.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/11fV-BR78feT8m1WAGpNYT8bZHVqMFje3
"""

# Commented out IPython magic to ensure Python compatibility.
import json
import pandas as pd
import numpy as np
import torch
from pathlib import Path
from torch.utils.data import Dataset, DataLoader
import pytorch_lightning as pl
from pytorch_lightning.callbacks import ModelCheckpoint
from pytorch_lightning.loggers import TensorBoardLogger
from sklearn.model_selection import train_test_split
from termcolor import colored
import textwrap
from transformers import (
     AdamW,
     T5ForConditionalGeneration,
     T5TokenizerFast as T5Tokenizer
)
from tqdm.auto import tqdm
import seaborn as sns
from pylab import rcParams
import matplotlib.pyplot as plt
from matplotlib import rc

# %matplotlib inline
# %config InLineBackend.figure_format = 'rectina'
sns.set(style='whitegrid', palette = 'muted', font_scale = 1.2)
rcParams['figure.figsize'] = 16, 10

!pip install pytorch_lightning

!pip freeze > requirement.txt

df = pd.read_csv('news_summary.csv', encoding = 'latin-1')
df.head()

df = df[["text", "ctext"]]
df.head()

df.columns = ["summary","text"]
df = df.dropna()
df.head()

df.shape

train_df, test_df = train_test_split(df, test_size = 0.1)
train_df.shape , test_df.shape

class NewsSummaryDataset(Dataset):
  def __init__(self, data: pd.DataFrame, tokenizer: T5Tokenizer, text_max_token_len: int = 512, summary_max_token_len: int = 128):
    self.tokenizer = tokenizer
    self.data = data
    self.text_max_token_len = text_max_token_len
    self.summary_max_token_len = summary_max_token_len

  def __len__(self):
    return len(self.data)

  def __getitem__(self, index: int):
    data_row = self.data.iloc[index]
    text = data_row["text"]
    summary = data_row["summary"]

    text_encoding = self.tokenizer(
        text,
        max_length=self.text_max_token_len,
        padding="max_length",
        truncation=True,
        return_attention_mask=True,
        add_special_tokens=True,
        return_tensors="pt"
    )

    summary_encoding = self.tokenizer(
        summary,
        max_length=self.summary_max_token_len,
        padding="max_length",
        truncation=True,
        return_attention_mask=True,
        add_special_tokens=True,
        return_tensors="pt"
    )

    labels = summary_encoding["input_ids"]
    labels[labels == 0] = -100

    return {
        "text": text,
        "summary": summary,
        "text_input_ids": text_encoding["input_ids"].flatten(),
        "text_attention_mask": text_encoding["attention_mask"].flatten(),
        "labels": labels.flatten(),
        "labels_attention_mask": summary_encoding["attention_mask"].flatten()
    }

"""class named **NewsSummaryDataset** that inherits from the Dataset class, which is a basic datastructure for PyTorch to interact with datasets. This class is used to prepare news data for training or evaluating a summarization model.

Overall, this class provides a convenient way to preprocess news data for a summarization model. It tokenizes the text and summary, creates attention masks, and handles padding and truncation. This allows the model to focus on the most important parts of the text and summary, and ignore the padding tokens.

# New Section

__init__: This is the constructor method for the class. It initializes the following attributes:

tokenizer: An instance of the Hugging Face's tokenizer, which is used to convert text into a format that can be processed by a model.
data: A Pandas DataFrame containing the news data, where each row has two columns: "text" and "summary".
text_max_token_len: An integer representing the maximum number of tokens for the input text.
summ_max_token_len: An integer representing the maximum number of tokens for the summary.

__getitem__: This method returns a dictionary containing the input data for a single sample in the dataset. It takes an index as an argument and performs the following steps:

Retrieves the data row at the specified index.
Tokenizes the text and summary using the tokenizer attribute.
Creates a mask for the input text and summary, where 1 indicates a token is present and 0 indicates a padding token.
Sets the masked tokens to -100, which tells the model to ignore these tokens during training.
Returns a dictionary containing the following keys:
text: The original text.
summary: The original summary.
text_input_ids: The tokenized text.
text_attenstion_mask: The attention mask for the text.
labels: The tokenized summary.
labels_attension_mask: The attention mask for the summary.
"""

class NewsSummaryDataModule(pl.LightningDataModule):
  def __init__(self, train_df: pd.DataFrame, test_df: pd.DataFrame, tokenizer: T5Tokenizer, batch_size = 8,
               text_max_token_len: int = 512, summary_max_token_len: int = 128):
    super().__init__()

    self.train_df = train_df
    self.test_df = test_df
    self.batch_size = batch_size
    self.tokenizer = tokenizer
    self.text_max_token_len = text_max_token_len
    self.summary_max_token_len = summary_max_token_len


  def setup(self, stage=None):
    self.train_dataset = NewsSummaryDataset(
        self.train_df,
        self.tokenizer,
        self.text_max_token_len,
        self.summary_max_token_len,
    )
    self.test_dataset = NewsSummaryDataset(
        self.test_df,
        self.tokenizer,
        self.text_max_token_len,
        self.summary_max_token_len,
    )

  def train_dataloader(self):
    return DataLoader(
        self.train_dataset,
        batch_size = self.batch_size,
        shuffle = True,
        num_workers = 2
    )


  def val_dataloader(self):
    return DataLoader(
        self.test_dataset,
        batch_size = self.batch_size,
        shuffle = False,
        num_workers = 2
    )


  def test_dataloader(self):
      return DataLoader(
        self.test_dataset,
        batch_size = self.batch_size,
        shuffle = False,
        num_workers = 2
    )

Model_Name = "t5-base"
tokenizer = T5Tokenizer.from_pretrained(Model_Name)

text_token_counts, summary_token_counts = [] ,[]
for _, row in train_df.iterrows():
  text_token_count = len(tokenizer.encode(row["text"]))
  text_token_counts.append(text_token_count)

  summary_token_count = len(tokenizer.encode(row["summary"]))
  summary_token_counts.append(summary_token_count)

fig, (ax1, ax2) = plt.subplots(1,2)
sns.histplot(text_token_counts, ax=ax1)
ax1.set_title("Full text token count")
sns.histplot(summary_token_counts, ax = ax2)
ax2.set_title("Full Summary token count")

N_Epochs = 3
Batch_Size = 8
data_module = NewsSummaryDataModule(train_df, test_df, tokenizer, batch_size= Batch_Size)

class NewsDataModel(pl.LightningModule):
    def __init__(self):
        super().__init__()
        self.model = T5ForConditionalGeneration.from_pretrained(Model_Name, return_dict=True)

    def forward(self, input_ids, attention_mask, decoder_attention_mask, labels=None):
        output = self.model(
            input_ids,
            attention_mask=attention_mask,
            labels=labels,
            decoder_attention_mask=decoder_attention_mask
        )
        return output.loss, output.logits

    def training_step(self, batch, batch_idx):
        input_ids = batch["text_input_ids"]
        attention_mask = batch["text_attention_mask"]
        labels = batch["labels"]
        labels_attention_mask = batch["labels_attention_mask"]

        loss, outputs = self(
            input_ids=input_ids,
            attention_mask=attention_mask,
            decoder_attention_mask=labels_attention_mask,
            labels=labels
        )

        self.log("train_loss", loss, prog_bar=True, logger=True)
        return loss

    def validation_step(self, batch, batch_idx):
        input_ids = batch["text_input_ids"]
        attention_mask = batch["text_attention_mask"]
        labels = batch["labels"]
        labels_attention_mask = batch["labels_attention_mask"]

        loss, outputs = self(
            input_ids=input_ids,
            attention_mask=attention_mask,
            decoder_attention_mask=labels_attention_mask,
            labels=labels
        )

        self.log("validation_loss", loss, prog_bar=True, logger=True)
        return loss

    def test_step(self, batch, batch_idx):
        input_ids = batch["text_input_ids"]
        attention_mask = batch["text_attention_mask"]
        labels = batch["labels"]
        labels_attention_mask = batch["labels_attention_mask"]

        loss, outputs = self(
            input_ids=input_ids,
            attention_mask=attention_mask,
            decoder_attention_mask=labels_attention_mask,
            labels=labels
        )

        self.log("test_loss", loss, prog_bar=True, logger=True)
        return loss

    def configure_optimizers(self):
        return AdamW(self.parameters(), lr=0.0001)

model = NewsDataModel()

# Commented out IPython magic to ensure Python compatibility.
# %load_ext tensorboard
# %tensorboard --logdir ./lightning_logs

checkpoint_callback = ModelCheckpoint(
    dirpath="checkpoints",
    filename="best-checkpoint",
    save_top_k=1,
    verbose = True,
    monitor = "validation_loss",
    mode="min"
)

logger = TensorBoardLogger("lightning_logs", name="news_summary")

trainer = pl.Trainer(
    logger = logger,
    callbacks=[checkpoint_callback],
    max_epochs = N_Epochs,
    accelerator="auto",
)

trainer.fit(model, data_module)

# Assuming you have a GPU available, otherwise it will fall back to CPU
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
trained_model = NewsDataModel.load_from_checkpoint(
    trainer.checkpoint_callback.best_model_path
)
trained_model.freeze()
trained_model.to(device)

def summarize(text):
  text_encoding = tokenizer(
      text,
      max_length = 512,
      padding = "max_length",
      truncation = True,
      return_attention_mask = True,
      add_special_tokens = True,
      return_tensors = "pt"
  )
  # Move the input tensors to the same device as the model
  input_ids = text_encoding["input_ids"].to(device)
  attention_mask = text_encoding["attention_mask"].to(device)

  print(f"Input IDs device after move: {input_ids.device}")
  print(f"Attention mask device after move: {attention_mask.device}")
  print(f"Model device: {next(trained_model.model.parameters()).device}")

  # Ensure the model components are also moved to the correct device
  trained_model.model.to(device)
    # Logging for debugging


  generated_ids = trained_model.model.generate(
        input_ids=input_ids,
        attention_mask=attention_mask,
        max_length=150,
        num_beams=2,
        repetition_penalty=2.5,
        length_penalty=1.0,
        early_stopping=True,
  )

    # Logging for debugging
  print(f"Generated IDs device: {generated_ids.device}")

  preds =  [
      tokenizer.decode(gen_id, skip_cancel_tokens=True, clean_up_tokenization_spaces = True)
      for gen_id in generated_ids
  ]

  return "".join(preds)

sample_row = test_df.iloc[0]
text = sample_row["text"]
model_summary = summarize(text)
print(model_summary)

text

sample_row["summary"]

model_summary

from google.colab import drive

# Mount Google Drive
drive.mount('/content/drive')

# Assuming you have a GPU available, otherwise it will fall back to CPU
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Save the trained model's state dictionary
model_save_path = '/content/drive/MyDrive/news_data_model.pth'
torch.save(trained_model.state_dict(), model_save_path)

# Later, load the model's state dictionary into a new model instance
new_model = NewsDataModel()
new_model.load_state_dict(torch.load(model_save_path))
new_model.to(device)
new_model.eval()  # Set the model to evaluation mode if needed

# Example function to summarize text using the loaded model
def summarize_with_loaded_model(text, model):
    text_encoding = tokenizer(
        text,
        max_length=512,
        padding="max_length",
        truncation=True,
        return_attention_mask=True,
        add_special_tokens=True,
        return_tensors="pt"
    )

    # Move the input tensors to the same device as the model
    input_ids = text_encoding["input_ids"].to(device)
    attention_mask = text_encoding["attention_mask"].to(device)

    generated_ids = model.model.generate(
        input_ids=input_ids,
        attention_mask=attention_mask,
        max_length=150,
        num_beams=2,
        repetition_penalty=2.5,
        length_penalty=1.0,
        early_stopping=True,
    )

    preds = [
        tokenizer.decode(gen_id, skip_special_tokens=True, clean_up_tokenization_spaces=True)
        for gen_id in generated_ids
    ]

    return "".join(preds)

# Use the loaded model for summarization
sample_row = test_df.iloc[0]
text = sample_row["text"]
model_summary = summarize_with_loaded_model(text, new_model)
print(model_summary)