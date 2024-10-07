"""
This script is an Azure Function, which is activated when a blob is uploaded
in a specified container allocated in the cloud, manage the blob and upload another blob
that contains a summary in pdf file in the same container


I have downloaded(through my local cmd) the next sdk to my virtual environment, 
#install SDK for azure functions
pip install azure-functions
#install the SDK of Azure Storage Blob
pip install azure-storage-blob
#To be able to use the stopwords
pip install nltk
#To use OpenAI
pip install openai
#To import Python library of PDF
pip install fpdf

"""
#import the azure.functions module
import azure.functions as func
#to log messages during the execution
import logging

#Library to import the json
import json
#Lbrary that will allow us to clean symbols(not relevant)
import nltk
#Library for the stopwords
from nltk.corpus import stopwords

#Just in case we need to download stopwords
nltk.download('stopwords')

#Libraries for use the resource of OpenAI that will do the summary
import openai 
#Library for regular expression
import re
#To work with environment variables
import os

#Work with PDF
from fpdf import FPDF

#Work with blobs
from azure.storage.blob import BlobServiceClient



def filter_of_confidence(doc, threshold):
    #Now I create function thet removes the part of the data that we feel that
    #hasn't been extracted in a right way with the OCR, because of its confidence

    #PRE: doc is one of the components(dictionary) of the main list (composed of many documents) and 
    #threshold the minimum "confidence" of the "words" we want to mantain
    #POST: returns the document in same format with the "words" that have the key of "confidence" more than threshold, 
    #deleting the keys "selection marks", "width", "height" and "unit" from the "content" key of each page because aren't relevant

   #Initialize a new dictionary for the filtered document, maintaining the format
    filtered_doc = {
        'doc_id': doc['doc_id'],  #Preserve doc_id
        'content': []
    }
    
    #Iterate over the pages in the document
    for page in doc['content']:
        #Initialize a new page structure with page_number
        filtered_page = {
            'page_number': page['page_number'],  #Preserve page_number
            'words': []  #This will hold filtered words
        }

        #Filter words based on confidence
        for word in page['words']:
            if word.get('confidence', 0) > threshold:
                #Preserve the whole word structure (content and confidence together)
                filtered_page['words'].append({'content': word['content'],'confidence': word['confidence']})
        
        #Add the filtered page to the content list
        filtered_doc['content'].append(filtered_page)
    
    return filtered_doc

def filter_data_by_confidence(data, threshold):
    #PRE: data is the whole data(composed of dictionaries, each document is one dictionary) we want to filter by confidence
    #POST: returns the data in same format but filtered by confidence
    return [filter_of_confidence(doc, threshold) for doc in data]



def clean_words(words):
    #PRE: words is a list of dictionaries, which every dictionary has at least a 'content' key
    #POST: return a list of strings, without stopwords(words with a stopword in the key 'content')

    stop_words=set(stopwords.words('english'))
    return [word['content'] for word in words if word['content'].lower() not in stop_words]

def filter_of_stopwords(data):
    #PRE: data has a json format and has been filtered by confidence
    #POST: returns data in json format, but now 'words' is returned as a list of 
    #strings(with all the words of each page filtered)

    filtered_by_stopwords = []
    
    #Iterate over each document
    for doc in data:
        cleaned_content = []
        
        #Iterate over each page in the document
        for page in doc['content']:
            #Clean the words (remove stopwords)
            cleaned_words = clean_words(page['words'])
            
            #Add cleaned data to the content
            cleaned_content.append({'page_number': page['page_number'],'words': cleaned_words})
        
        #Add the cleaned document to the processed list
        filtered_by_stopwords.append({'doc_id': doc['doc_id'],'content': cleaned_content})
    
    return filtered_by_stopwords


def json_to_text_with_metadata(data):
    #We want to transform the json in raw text to be sent to the AI
    #PRE: data must be a json with the next format
    #  [{"doc_id": docNum1, 
    #    "content":[{"page_number": pageNum1,
    #                "words":["word1","workd2",...]},   //end of the page1 of the doc1
    #               {"page_number": pageNum2,
    #                "words":[...]},{...}]  //end of content of the doc1
    #   {"doc_id": docNum2,
    #    "content": ...}
    #   {...}]     //end of the data
    #POST: returns the filtered content of each document and each page 
    #in an string(but specifying document and page content)

    #With this function we want to have the data in linear format, because
    #some NPL services would process better the data in this format
   
    text_content = []

    #Go through all the documents in the data
    for document in data:
        doc_id = document['doc_id'] 
        
        #Go through all the pages on each document
        for page in document['content']:
            page_number = page['page_number'] 
            #Add the number of document and page before the words 
            text_content.append(f"\n[Document {doc_id}, Page {page_number}]\n")
            #Add the words of each page
            text_content.extend(page['words'])
    #Return the list of words into continous text
    return ' '.join(text_content) 

def cleaner_of_data(data):

    #Filter de data by confidence
    filter1=filter_data_by_confidence(data,0.8)
    #Filter the data (that has been filtered by confidence), by stopwords
    filter2=filter_of_stopwords(filter1)
    #Write the json document into continous text, specifying Document and Page numbers
    continuousText=json_to_text_with_metadata(filter2)
    
    return continuousText

def connection_to_data(myblob:func.InputStream):
    #PRE:myblob is the new blob uploaded in a certain container in the cloud
    #POST: returns the json file saved in the blob
   
    try:
        #Read the content of the blob
        blob_data=myblob.read().decode('utf-8')
        
        #Convert the blob into json format
        jsonData=json.loads(blob_data)

        return jsonData

    except Exception as e:
        logging.error("Error obtaining the data from the blob")
        return None
    


#From this Python function, we could divide the code creating another Azure Function,
#one for the Step1(cleaning) and other for the Step2(summarizing)


def extract_documents_and_pages(importantData):
    #PRE: immportantData has this format:
    #[Document 1, Page 1]
    #...
    #[Document 1, Page 2]
    #...
    #POST: returns the same information but in json format 
    
    #With this function we want to know from where is obtaining the openAI resource
    #the information of each point in the summary, I know I'm repeating myself but we 
    #need this function to know from which parts of the data the summerizer is obtaining 
    #the points of the summary
    documents = []
    current_document = None
    current_page = None
    current_text = []

    #Regex to detect lines like '[Document X, Page Y]'
    pattern = re.compile(r"\[Document (\d+), Page (\d+)\]")

    for line in importantData.splitlines():
        match = pattern.match(line.strip())
        if match:
            #If we already have accumulated text, save the previous document's content
            if current_document and current_page and current_text:
                documents.append({
                    'doc_id': current_document,
                    'page_number': current_page,
                    'text': ' '.join(current_text)
                })

            #Start a new document/page
            current_document = match.group(1)
            current_page = match.group(2)
            current_text = []
        else:
            #Accumulate text for the current document and page
            current_text.append(line.strip())

    #Add the last document/page to the list if available
    if current_document and current_page and current_text:
        documents.append({
            'doc_id': current_document,
            'page_number': current_page,
            'text': ' '.join(current_text)
        })

    return documents


def summarize_with_openai(importantData):
    #PRE: immportantData has this format:
    #[Document 1, Page 1]
    #...
    #[Document 1, Page 2]
    #...
    #POST: returns the final summary with metadata(which document
    #and page) in a sequence of points
    try:
        # Get API key and endpoint from environment variables
        api_key = os.getenv("OPENAI_API_KEY")
        endpoint = os.getenv("OPENAI_ENDPOINT")

        if not api_key or not endpoint:
            raise ValueError("API key or endpoint for OpenAI is not configured.")

        # Configure the OpenAI client
        openai.api_type = "azure"
        openai.api_key = api_key
        openai.api_base = endpoint
        openai.api_version = "2023-06-01-preview"

        # Extract documents and pages from the provided data
        documents = extract_documents_and_pages(importantData)

        #Create a prompt that combines the document text and asks for a summary with document and page references
        text_to_summarize = ' '.join([f"Document {doc['doc_id']} Page {doc['page_number']}: {doc['text']}" for doc in documents])

        #Prompt for OpenAI
        MYprompt = f"Summarize the following content by extracting the most important points and indicating which document and page each point is from:\n{text_to_summarize}"

        #Call the OpenAI API to generate the summary
        response = openai.Completion.create(
            #Adjust the engine based on your Azure OpenAI configuration
            engine="text-davinci-003",  
            prompt=MYprompt,
            max_tokens=1000,  #Adjust token limit as needed
            n=1,
            stop=None,
            temperature=0.7
        )

        #Extract the generated summary, because openAI response is in json format and we only want the clean text output
        summary_text = response.choices[0].text.strip()

        #Return the summary text with document and page references
        return summary_text

    except Exception as e:
        logging.error(f"Error calling OpenAI API: {e}")
        #At this point we will see an error in the Logs of Azure(calling to the openAI resource)
        return None


#At this point we could create another Azure function, for verifying(step3)

def validate_summary_structure(summary_text):
    #PRE: summary_text is the summary that openAI resource has produce
    #POST: return true if the summary is schematic and standarised and false in other case
    
    #Validates the following structure structure: Point followed by [Document X, Page Y].
    
    #Split the summary into lines for validation
    summary_points = summary_text.splitlines()
    #Regular expression we want to find
    pattern = re.compile(r".+\[Document \d+, Page \d+\]$")  # Regex pattern to match the expected structure

    valid = True
    for i, point in enumerate(summary_points, 1):
        if not pattern.match(point.strip()):
            logging.error(f"Summary point {i} does not match the expected format: {point}")
            valid = False

    if valid:
        logging.info("Summary structure is valid.")
        #At this point we will see in the logs of Azure that the summary is valid
    else:
        logging.error("Summary structure is invalid.")
        #At this point we will see in the logs of Azure that the summary isn't valid

    return valid

#At this point we could create another Azure function to create the single response(final summary) we are looking for,
#which I have choosen to be a PDF because is the more general 

def create_pdf_from_summary(summary_text, pdf_path):
    #PRE: summary_text is a string that contains the summary
    #POST: returns pdf_path(after create the pdf)
    try:
        #Create the pdf
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        #Split lines of the string summary_text(taking each point)
        points = summary_text.split("\n")
        #Add the points into the pdf
        for point in points:
            pdf.cell(200, 10, txt=point, ln=True)

        #Save the pdf in pdf_path
        pdf.output(pdf_path)
        logging.info(f"PDF generated at {pdf_path}")
        return pdf_path

    except Exception as e:
        logging.error(f"Error generating PDF: {e}")
        return None
    
#We could create an extra Azure function just to decide what to do with the result,
#in my case I have choosen creating a blob in the same container that THE INITIAL DATA WAS UPLOADED
                                           
def upload_pdf_to_blob(container_name, blob_name, pdf_path):
    #PRE: pdf_path is the path of the pdf we have created, blob_name is the name of the blob in which
    #we want to save the pdf, container_name name is the name of the container in which will be allocated the blob with the pdf
    #POST: will upload the pdf in a blob(allocated in the container_name)
    try:
        #Get the connection string from environment variables
        connection_string = os.getenv("ssttoorraaggee1_STORAGE")

        if not connection_string:
            raise ValueError("Azure Storage connection string is not configured properly.")

        #Create a BlobServiceClient object to interact with the Blob service
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)

        #Get the reference to the container
        container_client = blob_service_client.get_container_client(container_name)

        #Create a blob client to upload the PDF
        blob_client = container_client.get_blob_client(blob_name)

        #Upload the file to the blob
        with open(pdf_path, "rb") as pdf_file:
            #Overwrite the content if the blob already exists
            blob_client.upload_blob(pdf_file, overwrite=True)  

        logging.info(f"PDF uploaded successfully to {container_name}/{blob_name}")
        return f"PDF uploaded successfully to {container_name}/{blob_name}"

    except Exception as e:
        logging.error(f"Error uploading PDF to blob: {e}")
        return None

app = func.FunctionApp()


@app.blob_trigger(arg_name="myblob", path="container1/{name}",
                               connection="ssttoorraaggee1_STORAGE") 
#blob_tigger activates the function when a new blob is uploaded in the specified container located in the cloud(resource) secifies
#arg_name is the variable we are going to use in the function to refer the blob
#path is the route of the container defined in the cloud
#connection is the configuration(defined in local.settings.json) that we are going to use to 
#access to the container in the cloud, we can se in the local settings thet is the Connection 
#String of the resource located in the cloud
def cleanerFunction(myblob: func.InputStream):
    logging.info(f"Python blob trigger function processed blob"
                f"Name: {myblob.name}"
                f"Blob Size: {myblob.length} bytes")

    #Gets the data of the blob that has been uploaded in json format
    json_data=connection_to_data(myblob)

    if json_data:
        #Clean data
        importantData=cleaner_of_data(json_data)
        logging.info(f"Data after cleaning: {importantData}")
        #At this point we will see importantData the in the Logs of Azure


        #Create the final summary
        final_summary=summarize_with_openai(importantData)
        
        if final_summary:
            logging.info(f"Final summary: {final_summary}")
            
            #Validate the summary structure
            is_valid = validate_summary_structure(final_summary)
            
            if is_valid:
                #Create the final response in a temporary storage
                #This paths refers to the temporary storage in Azure(consider
                #that the function is deployed in a Linux OS). It is known functions developed
                #with Python are more robust if are deployed in a Linux OS
                pdf_path="/tmp/summary_report.pdf"
                finalPdf=create_pdf_from_summary(final_summary,pdf_path)

                if finalPdf:
                    #Upload the final response(pdf) in a blob named "summary_report.pdf"
                    upload_pdf_to_blob("container1","summary_report.pdf",finalPdf)

            else:
                logging.error("Final summary failed validation.")
        
        else:
            logging.error("Creation of the final summary(with openAI) failed.")
    

    else:
        logging.error("Fail converting the blob in json")


