def import_stages():
    from .stage_1_initialization import InitializationStage

    return {
        "InitializationStage": InitializationStage
    }
