from dataclasses import dataclass, field


@dataclass
class CompileResult:
    errors: list[str] = field(default_factory=list)
    logs:   list[dict] = field(default_factory=list)

    def ok(self) -> bool:
        return len(self.errors) == 0

    def log(self, level: str, text: str):
        self.logs.append({"level": level, "text": text})

    def error(self, text: str, fix: str = ""):
        self.errors.append(text)
        self.logs.append({"level": "error", "text": text})
        if fix:
            self.logs.append({"level": "error", "text": f"Fix: {fix}"})

    def warn(self, text: str):
        self.logs.append({"level": "warn", "text": text})

    def success(self, text: str):
        self.logs.append({"level": "success", "text": text})

    def info(self, text: str):
        self.logs.append({"level": "info", "text": text})
