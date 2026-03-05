import os

import pandas as pd
from tqdm import tqdm

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_ollama import OllamaLLM as Ollama


def get_response(question, context):
    prompt = f"""
    Given the following context: {context} \n
    Could you please answer the following question: {question} \n
    Respond with a clear yes or no, plus a justification. \n
    Only respond based on the information provided in the context.
    """
    model = Ollama(model='llama3.2', temperature=0, top_k=10, top_p=0.3)
    response = model.invoke(prompt)
    return response


def main():

    # datastore path
    ticker = 'QAN'
    start_year = 2018
    end_year = 2020
    datastore_path = f"datastores/faiss_{ticker}_{start_year}_{end_year}"

    # embedding object
    print("loading embedding matrix")
    embedding = HuggingFaceEmbeddings()

    # load cissa questionare
    print("loading cissa questionare")
    df_cissa_questions = pd.read_csv("data/template_cissa_questionare.csv")
    list_cissa_questions = df_cissa_questions["question"].tolist()

    # list responses
    list_responses = []
    list_justifications = []
    for question in tqdm(list_cissa_questions):
        print("retrieve relevant context")
        new_db = FAISS.load_local(datastore_path, embedding, allow_dangerous_deserialization=True)
        res = new_db.similarity_search(question)

        print("generate response")
        print(f"Question: {question}")
        output = get_response(question, res[0])

        if output.lower().strip().startswith('yes'):
            list_responses.append(1)
        else:
            list_responses.append(0)

        list_justifications.append(output)
        print(output)

    # save responses
    df_cissa_questions["response"] = list_responses
    df_cissa_questions["justification"] = list_justifications
    # create output directory if it does not exist
    os.makedirs(f"output/{ticker}", exist_ok=True)
    df_cissa_questions.to_csv(
        f"output/{ticker}/sowc_llama3.2_llm_responses_{start_year}_{end_year}_prompt_context_restriction.csv",
        index=False)


if __name__ == '__main__':
    main()
