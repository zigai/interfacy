from interfacy_cli.click_parser import ClickParser


def process_text(input_data: str):
    return f"Processed text: {input_data}"


def count_words(text: str):
    return f"Word count: {len(text.split())}"


parser = ClickParser(pipe_target={"process-text": "input_data", "count-words": "text"})
parser.add_command(process_text)
parser.add_command(count_words)
parser.run()
