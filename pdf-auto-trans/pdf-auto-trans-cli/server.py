import os
import sys
import json
import argparse
from flask import Flask, request, jsonify
from werkzeug.serving import make_server
import threading

from config import (
    API_PROVIDERS,
    TRANSLATION_CONFIG,
    PDF_CONFIG,
    GLOSSARY_FILE,
    INPUT_PDF_FOLDER,
    OUTPUT_FOLDER,
    SERVER_CONFIG,
    DEFAULT_PROVIDER_ORDER,
    get_enabled_providers_in_order,
)
from prompt_template import TRANSLATION_PROMPT
from text_extractor import TextExtractor
from translator import MangaTranslator
from pdf_annotator import PDFAnnotator

app = Flask(__name__)

translator = None
extractor = None
annotator = None

def init_components(api_config_list=None, translation_config=None, pdf_config=None):
    global translator, extractor, annotator
    
    if api_config_list is None:
        api_config_list = []
        for provider_name in get_enabled_providers_in_order():
            if provider_name in API_PROVIDERS:
                provider = API_PROVIDERS[provider_name]
                if provider.get("enabled", False) and provider.get("api_key"):
                    api_config_list.append(provider)
    
    if translation_config is None:
        translation_config = TRANSLATION_CONFIG.copy()
        translation_config["manga_prompt_template"] = TRANSLATION_PROMPT
    
    if pdf_config is None:
        pdf_config = PDF_CONFIG
    
    if api_config_list:
        translator = MangaTranslator(api_config_list, translation_config, GLOSSARY_FILE)
    
    extractor = TextExtractor(
        rubi_size=pdf_config.get("rubi_size", 5.0),
        x_position_threshold=pdf_config.get("x_position_threshold", 0.3),
        y_position_threshold=pdf_config.get("y_position_threshold", 0.5)
    )
    annotator = PDFAnnotator(
        rubi_size=pdf_config.get("rubi_size", 5.0),
        x_position_threshold=pdf_config.get("x_position_threshold", 0.3),
        y_position_threshold=pdf_config.get("y_position_threshold", 0.5),
        include_font_info=pdf_config.get("include_font_info", False),
        font_scale=pdf_config.get("font_scale", 1.0)
    )


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "ok",
        "service": "manga-pdf-translator"
    })


@app.route('/api/extract', methods=['POST'])
def extract_text():
    try:
        data = request.get_json() or {}
        input_folder = data.get('input_folder', INPUT_PDF_FOLDER)
        rubi_size = data.get('rubi_size', 5.0)
        x_threshold = data.get('x_position_threshold', 0.3)
        y_threshold = data.get('y_position_threshold', 0.5)
        
        temp_extractor = TextExtractor(rubi_size, x_threshold, y_threshold)
        blocks = temp_extractor.merge_and_extract(input_folder)
        
        return jsonify({
            "success": True,
            "blocks_count": len(blocks),
            "data": blocks
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/translate', methods=['POST'])
def translate_text():
    try:
        data = request.get_json() or {}
        
        if not translator:
            return jsonify({
                "success": False,
                "error": "Translator not initialized. Please configure API first."
            }), 400
        
        input_folder = data.get('input_folder', INPUT_PDF_FOLDER)
        rubi_size = data.get('rubi_size', 5.0)
        x_threshold = data.get('x_position_threshold', 0.3)
        y_threshold = data.get('y_position_threshold', 0.5)
        
        temp_extractor = TextExtractor(rubi_size, x_threshold, y_threshold)
        blocks = temp_extractor.merge_and_extract(input_folder)
        
        translated_blocks = translator.translate_text(blocks)
        
        return jsonify({
            "success": True,
            "blocks_count": len(translated_blocks),
            "data": translated_blocks
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/process', methods=['POST'])
def process_pdf():
    try:
        data = request.get_json() or {}
        
        if not translator or not extractor or not annotator:
            return jsonify({
                "success": False,
                "error": "Components not initialized. Please configure API first."
            }), 400
        
        input_folder = data.get('input_folder', INPUT_PDF_FOLDER)
        output_folder = data.get('output_folder', OUTPUT_FOLDER)
        base_filename = data.get('output_filename', 'translated_manga')
        filename_suffix = data.get('filename_suffix', '_translated')
        
        os.makedirs(output_folder, exist_ok=True)
        
        blocks = extractor.merge_and_extract(input_folder)
        
        translated_blocks = translator.translate_text(blocks)
        
        results = annotator.generate_all_outputs(
            input_folder, 
            translated_blocks, 
            output_folder,
            generate_original=data.get('generate_original', True),
            generate_translated=data.get('generate_translated', True),
            generate_txt=data.get('generate_txt', True),
            base_filename=base_filename,
            filename_suffix=filename_suffix
        )
        
        return jsonify({
            "success": True,
            "input_folder": input_folder,
            "results": results,
            "blocks_count": len(translated_blocks)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/config', methods=['POST'])
def configure():
    try:
        data = request.get_json() or {}
        
        api_config_list = data.get('api_config_list', [])
        translation_config = data.get('translation_config', TRANSLATION_CONFIG.copy())
        pdf_config = data.get('pdf_config', PDF_CONFIG)
        
        translation_config["manga_prompt_template"] = TRANSLATION_PROMPT
        
        init_components(api_config_list, translation_config, pdf_config)
        
        return jsonify({
            "success": True,
            "message": "Configuration updated successfully"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/providers', methods=['GET'])
def get_providers():
    providers_info = []
    for name, config in API_PROVIDERS.items():
        providers_info.append({
            "id": name,
            "name": config["name"],
            "enabled": config.get("enabled", False),
            "has_api_key": bool(config.get("api_key")),
            "model": config.get("model", "")
        })
    return jsonify({
        "success": True,
        "providers": providers_info
    })


@app.route('/api/glossary', methods=['GET', 'POST'])
def glossary():
    try:
        if request.method == 'GET':
            if not translator:
                return jsonify({
                    "success": False,
                    "error": "Translator not initialized"
                }), 400
            
            glossary_data = translator.glossary_manager.glossary
            return jsonify({
                "success": True,
                "glossary": glossary_data,
                "count": len(glossary_data)
            })
        
        else:
            data = request.get_json() or {}
            new_terms = data.get('terms', {})
            
            if not translator:
                return jsonify({
                    "success": False,
                    "error": "Translator not initialized"
                }), 400
            
            for jp, cn in new_terms.items():
                translator.glossary_manager.glossary[jp] = cn
            
            return jsonify({
                "success": True,
                "message": f"Added {len(new_terms)} terms to glossary"
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/translate/simple', methods=['POST'])
def translate_simple():
    try:
        data = request.get_json() or {}
        
        if not translator:
            return jsonify({
                "success": False,
                "error": "Translator not initialized. Please configure API first."
            }), 400
        
        text_lines = data.get('text', [])
        
        if isinstance(text_lines, str):
            text_lines = text_lines.split('\n')
        
        translated_lines = translator.translate_simple(text_lines)
        
        return jsonify({
            "success": True,
            "original_count": len(text_lines),
            "translated_count": len(translated_lines),
            "data": translated_lines
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


def run_server(host=None, port=None, debug=False):
    if host is None:
        host = SERVER_CONFIG.get('host', '0.0.0.0')
    if port is None:
        port = SERVER_CONFIG.get('port', 8078)
    
    init_components()
    app.run(host=host, port=port, debug=debug)


class ServerThread(threading.Thread):
    def __init__(self, host=None, port=None, debug=False):
        threading.Thread.__init__(self)
        self.host = host or SERVER_CONFIG.get('host', '0.0.0.0')
        self.port = port or SERVER_CONFIG.get('port', 8078)
        self.debug = debug
        self.server = None
        self._stop_event = threading.Event()
    
    def run(self):
        init_components()
        self.server = make_server(self.host, self.port, app, threaded=True)
        self.server.serve_forever()
    
    def stop(self):
        self._stop_event.set()
        if self.server:
            self.server.shutdown()


def main():
    parser = argparse.ArgumentParser(description='Manga PDF Translator MCP Server')
    parser.add_argument('--host', default=None, help='Server host')
    parser.add_argument('--port', type=int, default=None, help='Server port')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    port = args.port or SERVER_CONFIG.get('port', 8078)
    host = args.host or SERVER_CONFIG.get('host', '0.0.0.0')
    
    print(f"Starting Manga PDF Translator MCP Server...")
    print(f"API will be available at http://{host}:{port}")
    
    run_server(args.host, args.port, args.debug)


if __name__ == '__main__':
    main()
