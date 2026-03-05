import os

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings


def load_data(files_path, start_year, end_year):

    # List all the files in the directory
    list_years = [str(year) for year in range(start_year, end_year + 1)]
    files = []
    for year in list_years:
        files += [os.path.join(f'{files_path}/{year}', file) for file in os.listdir(f'{files_path}/{year}')]

    data = []
    # Iterate over all the files
    for file in files:
        # Only process PDF files
        if not file.endswith('.pdf'):
            continue
        # Load PDF file
        loader = PyPDFLoader(file)
        # Load and split the pages
        pages = loader.load_and_split()
        # Append the pages to the data
        data.extend(pages)

    return data


def main():

    ticker = 'COH'
    start_year = 2020
    end_year = 2022

    print("loading embedding matrix")
    embedding = HuggingFaceEmbeddings()

    print("loading data")
    data = load_data(f"./data/{ticker}_company_announcements", start_year=start_year, end_year=end_year)

    print("loading embeddings in vector db")
    db = FAISS.from_documents(data, embedding)
    print("saving index")
    db.save_local(f'datastores/faiss_{ticker}_{start_year}_{end_year}')
    print("process completed")


if __name__ == '__main__':
    main()
