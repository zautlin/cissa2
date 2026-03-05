# pylint: disable=too-many-locals
import numpy as np
import matplotlib.pyplot as plt


def main():

    # data
    human_scores = [10,  # Qantas
                    44,  # PEXA
                    53  # Cochlear
                    ]
    llm_scores = [16,  # Qantas
                  17,  # PEXA
                  23  # Cochlear
                  ]
    companies = ['Qantas', 'PEXA', 'Cochlear']

    # Correlation plot between human scores (x axis) and LLM scores (y axis)
    # Markers of different colors for each company
    colors = ['red', 'green', 'blue']
    for i, company in enumerate(companies):
        plt.scatter(human_scores[i], llm_scores[i], color=colors[i])
        plt.annotate(company, (human_scores[i], llm_scores[i]))
    plt.xlabel('Human Scores')
    plt.ylabel('LLM Scores')
    plt.title('Human vs LLM Scores')

    # add a trendline
    z = np.polyfit(human_scores, llm_scores, 1)
    p = np.poly1d(z)
    plt.plot(human_scores, p(human_scores), "r--")
    plt.show()

    # Compare scores by section
    sections = [
        'Mindset, Purpose and Governance',
        'Organisation, Culture and Innovation',
        'Products, Services, Production and Distribution',
        'Economic Sustainability'
    ]

    human_scores_qantas = [3, 8, 17, 25]
    human_scores_pexa = [26, 31, 100, 50]
    human_scores_cochlear = [29, 53, 100, 50]

    llm_scores_qantas = [12, 17, 33, 0]
    llm_scores_pexa = [35, 6, 17, 0]
    llm_scores_cochlear = [12, 36, 33, 0]

    # Plot human vs LLM scores for each in three different bar plots (one per company)
    # Half x area for human scores and half for LLM scores
    _, axs = plt.subplots(figsize=(15, 10))
    y_secs = np.arange(len(sections))
    # for i, company in enumerate(companies):
    axs.bar(y_secs - 0.2, human_scores_qantas, 0.4, color='green', label='Human Scores')
    axs.bar(y_secs + 0.2, llm_scores_qantas, 0.4,  color='blue', label='LLM Scores')
    axs.set_title('Qantas', fontsize=24)
    axs.set_ylabel('Scores', fontsize=20)
    axs.legend()
    axs.set_xticks([])
    # Set y axis limits
    axs.set_ylim(0, 100)
    plt.show()

    _, axs = plt.subplots(figsize=(15, 10))
    axs.bar(y_secs - 0.2, human_scores_pexa, 0.4, color='green', label='Human Scores')
    axs.bar(y_secs + 0.2, llm_scores_pexa, 0.4, color='blue', label='LLM Scores')
    axs.set_title('PEXA', fontsize=24)
    axs.set_ylabel('Scores', fontsize=20)
    axs.legend()
    axs.set_xticks([])
    axs.set_ylim(0, 100)
    plt.show()

    _, axs = plt.subplots(figsize=(15, 10))
    axs.bar(y_secs - 0.2, human_scores_cochlear, 0.4, color='green', label='Human Scores')
    axs.bar(y_secs + 0.2, llm_scores_cochlear, 0.4, color='blue', label='LLM Scores')
    axs.set_title('Cochlear', fontsize=24)
    axs.set_ylabel('Scores', fontsize=20)
    axs.legend()
    axs.set_xticks([])
    axs.set_ylim(0, 100)
    plt.show()

    # trendline for each company
    qantas_trend = [46, 37, 39, 49, 42]
    pexa_trend = [58, 56]
    cochlear_trend = [50, 58, 52, 55, 53]

    x_years = [2020, 2021, 2022, 2023, 2024]

    plt.plot(x_years, qantas_trend, label='Qantas', color='red')
    plt.plot(x_years[-2:], pexa_trend, label='PEXA', color='green')
    plt.plot(x_years, cochlear_trend, label='Cochlear', color='blue')
    plt.xlabel('Years')
    plt.ylabel('Scores')
    plt.title('Scores Trend (Llama 3.2)')
    plt.legend()
    plt.xticks(x_years)
    plt.xlim(2019.8, 2024.2)
    plt.show()


if __name__ == "__main__":
    main()
