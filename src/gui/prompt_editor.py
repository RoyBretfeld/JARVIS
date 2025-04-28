import json
import os
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTextEdit, QListWidget, QLabel, QMessageBox, QGroupBox, QDialogButtonBox, QInputDialog)
from PyQt6.QtCore import Qt

class PromptEditor(QDialog):
    def __init__(self, prompts_file: str, parent=None):
        super().__init__(parent)
        self.prompts_file = prompts_file
        self.setWindowTitle("System-Prompt Editor")
        self.setModal(True)
        
        # Lade Prompts zuerst
        self.current_prompts = self.load_prompts()
        
        # Rufe die KORREKTE UI-Initialisierungsmethode auf
        self.init_ui() 
        
    def init_ui(self):
        """Initialisiert die Benutzeroberfläche (die detaillierte Ansicht)"""
        layout = QHBoxLayout()
        
        # Linke Seite - Regelliste
        rules_group = QGroupBox("Verhaltensregeln")
        rules_layout = QVBoxLayout()
        
        self.rules_list = QListWidget()
        self.rules_list.addItems(self.current_prompts["system_prompt"]["rules"])
        rules_layout.addWidget(self.rules_list)
        
        # Buttons für Regelmanagement
        button_layout = QHBoxLayout()
        self.add_rule_btn = QPushButton("Regel hinzufügen")
        self.edit_rule_btn = QPushButton("Regel bearbeiten")
        self.delete_rule_btn = QPushButton("Regel löschen")
        
        self.add_rule_btn.clicked.connect(self.add_rule)
        self.edit_rule_btn.clicked.connect(self.edit_rule)
        self.delete_rule_btn.clicked.connect(self.delete_rule)
        
        button_layout.addWidget(self.add_rule_btn)
        button_layout.addWidget(self.edit_rule_btn)
        button_layout.addWidget(self.delete_rule_btn)
        rules_layout.addLayout(button_layout)
        rules_group.setLayout(rules_layout)
        
        # Rechte Seite - Persönlichkeitseinstellungen
        personality_group = QGroupBox("Persönlichkeit")
        personality_layout = QVBoxLayout()
        
        # Content
        content_label = QLabel("Basis-Prompt:")
        self.content_edit = QTextEdit()
        self.content_edit.setText(self.current_prompts["system_prompt"]["content"])
        personality_layout.addWidget(content_label)
        personality_layout.addWidget(self.content_edit)
        
        # Tone
        tone_label = QLabel("Tonfall:")
        self.tone_edit = QTextEdit()
        self.tone_edit.setText(self.current_prompts["system_prompt"]["personality"]["tone"])
        self.tone_edit.setMaximumHeight(50)
        personality_layout.addWidget(tone_label)
        personality_layout.addWidget(self.tone_edit)
        
        # Style
        style_label = QLabel("Stil:")
        self.style_edit = QTextEdit()
        self.style_edit.setText(self.current_prompts["system_prompt"]["personality"]["style"])
        self.style_edit.setMaximumHeight(50)
        personality_layout.addWidget(style_label)
        personality_layout.addWidget(self.style_edit)
        
        personality_group.setLayout(personality_layout)
        
        # Füge beide Seiten zum Layout hinzu
        layout.addWidget(rules_group)
        layout.addWidget(personality_group)
        
        # Buttons unten
        bottom_layout = QHBoxLayout()
        save_btn = QPushButton("Speichern")
        cancel_btn = QPushButton("Abbrechen")
        
        save_btn.clicked.connect(self.save_prompts)
        cancel_btn.clicked.connect(self.reject)
        
        bottom_layout.addWidget(save_btn)
        bottom_layout.addWidget(cancel_btn)
        
        # Hauptlayout
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(bottom_layout)
        
        self.setLayout(main_layout)
        
        # Dark Theme
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            QGroupBox {
                border: 1px solid #3d3d3d;
                color: #ffffff;
                font-weight: bold;
                margin-top: 1ex;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }
            QTextEdit, QListWidget {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
            }
            QPushButton {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                padding: 5px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
            QLabel {
                color: #ffffff;
            }
        """)
        
    def load_prompts(self):
        """Lädt die Prompts aus der JSON-Datei"""
        try:
            if os.path.exists(self.prompts_file):
                with open(self.prompts_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Fehler", f"Fehler beim Laden der Prompts: {str(e)}")
        return {
            "system_prompt": {
                "content": "",
                "rules": [],
                "personality": {
                    "tone": "",
                    "style": "",
                    "language": "Deutsch"
                }
            }
        }
        
    def save_prompts(self):
        """Speichert die Prompts in die JSON-Datei"""
        try:
            # Aktualisiere das Prompt-Dictionary
            self.current_prompts["system_prompt"]["content"] = self.content_edit.toPlainText()
            self.current_prompts["system_prompt"]["rules"] = [
                self.rules_list.item(i).text()
                for i in range(self.rules_list.count())
            ]
            self.current_prompts["system_prompt"]["personality"]["tone"] = self.tone_edit.toPlainText()
            self.current_prompts["system_prompt"]["personality"]["style"] = self.style_edit.toPlainText()
            
            # Speichere in Datei
            os.makedirs(os.path.dirname(self.prompts_file), exist_ok=True)
            with open(self.prompts_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_prompts, f, indent=4, ensure_ascii=False)
                
            QMessageBox.information(self, "Erfolg", "Prompts wurden erfolgreich gespeichert!")
            self.accept()
            
        except Exception as e:
            QMessageBox.warning(self, "Fehler", f"Fehler beim Speichern der Prompts: {str(e)}")
            
    def add_rule(self):
        """Fügt eine neue Regel hinzu"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Neue Regel")
        layout = QVBoxLayout()
        
        rule_edit = QTextEdit()
        layout.addWidget(rule_edit)
        
        buttons = QHBoxLayout()
        save_btn = QPushButton("Hinzufügen")
        cancel_btn = QPushButton("Abbrechen")
        
        save_btn.clicked.connect(lambda: self.save_new_rule(dialog, rule_edit.toPlainText()))
        cancel_btn.clicked.connect(dialog.reject)
        
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)
        
        dialog.setLayout(layout)
        dialog.exec_()
        
    def save_new_rule(self, dialog, rule):
        """Speichert eine neue Regel"""
        if rule.strip():
            self.rules_list.addItem(rule)
            dialog.accept()
        
    def edit_rule(self):
        """Bearbeitet die ausgewählte Regel"""
        current_item = self.rules_list.currentItem()
        if not current_item:
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Regel bearbeiten")
        layout = QVBoxLayout()
        
        rule_edit = QTextEdit()
        rule_edit.setText(current_item.text())
        layout.addWidget(rule_edit)
        
        buttons = QHBoxLayout()
        save_btn = QPushButton("Speichern")
        cancel_btn = QPushButton("Abbrechen")
        
        save_btn.clicked.connect(lambda: self.save_edited_rule(dialog, current_item, rule_edit.toPlainText()))
        cancel_btn.clicked.connect(dialog.reject)
        
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)
        
        dialog.setLayout(layout)
        dialog.exec_()
        
    def save_edited_rule(self, dialog, item, new_text):
        """Speichert die bearbeitete Regel"""
        if new_text.strip():
            item.setText(new_text)
            dialog.accept()
        
    def delete_rule(self):
        """Löscht die ausgewählte Regel"""
        current_item = self.rules_list.currentItem()
        if current_item:
            if QMessageBox.question(self, "Bestätigung", 
                                  "Möchten Sie diese Regel wirklich löschen?",
                                  QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                self.rules_list.takeItem(self.rules_list.row(current_item)) 