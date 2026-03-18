export const LANGUAGES = {
  ZH: "zh",
  EN: "en",
};

export const TRANSLATIONS = {
  [LANGUAGES.ZH]: {
    "box.safe": "\u5b89\u5168\u4e00\u70b9",
    "box.risky": "\u5192\u9669\u4e00\u70b9",
    "runner.level": "\u7b49\u7ea7",
    "runner.health": "\u751f\u547d",
    "runner.growth": "\u6210\u957f",
    "runner.miceCaught": "\u5df2\u5403\u8001\u9f20",
    "runner.language": "\u8bed\u8a00",
    "runner.languageToggle": "\u5207\u6362\u8bed\u8a00",
    "runner.languageToggleAria": "\u5207\u6362\u6e38\u620f\u8bed\u8a00",
    "runner.restart": "\u91cd\u6765\u4e00\u6b21",
    "runner.start": "\u8d77\u8dd1\u5427\uff0c\u8ba9\u8c93\u8dd1\u8d77\u6765\u3002",
    "runner.jump": "\u8df3\u8d77\u6765\uff01",
    "runner.levelUp": "\u957f\u5927\u4e86\uff01",
    "runner.catch": "\u4e00\u53e3\u5403\u6389\u4e86\u8001\u9f20\uff01",
    "runner.hit": "\u88ab\u66f4\u5f3a\u7684\u8001\u9f20\u7ffb\u56de\u6765\u4e86\uff01",
    "runner.fall": "\u8dea\u4e86\u4e00\u4e0b\uff0c\u4f46\u6211\u4eec\u7ee7\u7eed\u8dd1\u3002",
    "runner.gameOver": "\u6e38\u620f\u7ed3\u675f\uff0c\u518d\u8bd5\u4e00\u6b21\u5427\u3002",
    "runner.tip": "\u7528\u9f20\u6807\u5f15\u5bfc\u8c93\u8dd1\u5411\u524d\uff0c\u70b9\u51fb\u53ef\u4ee5\u8df3\u8d77\u6765\u3002",
    "runner.stage": "\u8dd1\u8f6e\u573a\u666f",
    "runner.mouse": "\u8001\u9f20",
    "stage.kitten.name": "\u5c0f\u5976\u732b",
    "stage.cat.name": "\u5927\u732b",
    "stage.fancy.name": "\u534e\u4e3d\u732b",
    "stage.kitten.emoji": "\u{1f431}",
    "stage.cat.emoji": "\u{1f408}",
    "stage.fancy.emoji": "\u2728",
  },
  [LANGUAGES.EN]: {
    "box.safe": "Safer",
    "box.risky": "Riskier",
    "runner.level": "Level",
    "runner.health": "Health",
    "runner.growth": "Growth",
    "runner.miceCaught": "Mice caught",
    "runner.language": "Language",
    "runner.languageToggle": "Switch language",
    "runner.languageToggleAria": "Toggle game language",
    "runner.restart": "Restart run",
    "runner.start": "Run, cat, run.",
    "runner.jump": "Jump!",
    "runner.levelUp": "Level up!",
    "runner.catch": "Mouse caught!",
    "runner.hit": "A stronger mouse hit back!",
    "runner.fall": "A fall hurt a bit, but the run continues.",
    "runner.gameOver": "Game over. Try again.",
    "runner.tip": "Steer with the mouse and click to jump.",
    "runner.stage": "Runner scene",
    "runner.mouse": "Mouse",
    "stage.kitten.name": "Kitten",
    "stage.cat.name": "Cat",
    "stage.fancy.name": "Fancy Cat",
    "stage.kitten.emoji": "\u{1f431}",
    "stage.cat.emoji": "\u{1f408}",
    "stage.fancy.emoji": "\u2728",
  },
};

export function getText(key, language = LANGUAGES.ZH) {
  return TRANSLATIONS[language]?.[key] ?? TRANSLATIONS[LANGUAGES.ZH]?.[key] ?? key;
}

export function toggleLanguage(language) {
  return language === LANGUAGES.ZH ? LANGUAGES.EN : LANGUAGES.ZH;
}

export function getBoxLabel(boxType, language = LANGUAGES.ZH) {
  return getText(`box.${boxType}`, language);
}

export function getStageDisplay(stageId, language = LANGUAGES.ZH) {
  return {
    name: getText(`stage.${stageId}.name`, language),
    emoji: getText(`stage.${stageId}.emoji`, language),
  };
}
