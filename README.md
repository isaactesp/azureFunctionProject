<h1>Azure Function</h1>

<h2>Context</h2>

#### We suppose that we have a suscription of Microsoft Cloud(Azure), in which we have the next resources:
- Storage Account with a container.
- Function App(where this project will be deployed).
- OpenAI service.

<h2>Specification</h2>
#### This Azure Function, developed with Python, runs everytime that a file is uploaded in the container. The file is supposed to be in json format, with data about many documents(part of the same "matter") that have been performed by an OCR, like the following: 
```
[
  {
    "doc_id": 1,
    "content": [
      {
        "page_number": 1,
        "width": 8.2639,
        "height": 11.6806,
        "unit": "inch",
        "words": [{"content": "Submission", "confidence": 0.994},{"content": "to", "confidence": 0.995},{...}],
        "selection_marks"=[]
      },
      {
        "page_number": 2,
        "width": 8.2639,
        "height": 11.6806,
        "unit": "inch",
        ...//words of page 2
      },//more pages
      {...}]
    },
    {
      "doc_id": 2,
      ...//content doc 2
  },
    ...//more documents
]
```

#### The function will manage the blob(storage solution of Azure) of data and will create another blob in the same container. This second blob will contain a pdf with a summary of the data by points.

<h2>Inner functions</h2>
#### The Function of Azure(cleanerFunction()) is divided in 5 steps: 
  1. Clean the data(which includes connecting to the blob in which is the data). Functions:
    - filter_of_confidence()
    - filter_data_by_confidence()
    - clean_words()
    - filter_of_stopwords()
    - json_to_text_with_metadata()
    - cleaner_of_data()
    - connection_to_data()    
  2. Summarize the cleaned data(which includes connecting to the OpenAI resource). Functions:
    - extract_documents_and_pages()
    - summarize_with_openai()
  3. Validate the summary(ensure the summary is in schematic format). Functions:
    - validate_summary_structure()
  4. Create pdf with the summary(will be allocate in a temporary storage in the cloud). Functions:
    - create_pdf_from_summary()
  5. Upload the summary at the container(with a blob client). Functions:
    - upload_pdf_to_blob()

#### (To be more effective run the function in a Linux OS, will be more robust)

    
      
        
        
          
  

