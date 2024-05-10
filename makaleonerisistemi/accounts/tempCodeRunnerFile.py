model = fasttext.load_model(hf_hub_download("facebook/fasttext-language-identification", "model.bin"))
fasttext_tokenizer = AutoTokenizer.from_pretrained("facebook/fasttext-language-identification")
fasttext_model = AutoModel.from_pretrained("facebook/fasttext-language-identification")
