# credit-meter

Mod do Claude Code que mostra, acima do campo de prompt, uma barra em tempo real com:

- 💳 gasto da sessão em US$ (o mesmo do `/cost`) e quanto custou o prompt atual
- uso do contexto da conversa
- uso dos limites do plano (5 horas e 7 dias), quando o plano informa

Cores: verde, amarelo a partir de 70% e vermelho a partir de 90%. O comando `/credit-meter` esconde ou mostra a barra.

## Instalar em toda sessão

O Claude Code carrega sozinho qualquer mod em `~/.claude/skills/<nome>`. O `install.sh` grava o mod lá. Ele não depende de nenhum outro arquivo, então dá para colar o conteúdo dele direto num script.

**No seu computador:**

```bash
bash credit-meter/install.sh
```

**No Claude Code na web (sessões na nuvem):** abra o menu do ambiente na barra de título da sessão → **Edit** → **Setup script** e cole o conteúdo de `install.sh`. Toda sessão nova desse ambiente já começa com a barra.

## Desenvolvimento

```bash
claude plugin validate credit-meter
claude plugin test credit-meter
```
