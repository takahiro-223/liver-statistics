"""プロジェクト共通の例外クラス。"""


class LiverStatisticsError(Exception):
    """本プロジェクトの基底例外。"""


class ImportDirectoryNotFoundError(LiverStatisticsError):
    """取り込み対象のフォルダが存在しない。"""


class NoImagesFoundError(LiverStatisticsError):
    """取り込み対象のフォルダに画像が1枚も無い。"""


class ImageReadError(LiverStatisticsError):
    """画像ファイルを開けない、または壊れている。"""


class OcrEngineUnavailableError(LiverStatisticsError):
    """Tesseract 本体が見つからない。"""


class InputError(LiverStatisticsError):
    """CLI の引数や設定値が不正。"""
