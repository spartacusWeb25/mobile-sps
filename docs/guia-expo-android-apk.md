# App mobile: rodar com Expo e gerar o APK

> Guia passo a passo — Expo CLI + Android Studio (emulador) ou celular Android + SDK. Siga as etapas na ordem; cada uma diz ONDE digitar, O QUE o comando faz e COMO SABER QUE DEU CERTO.

## Antes de começar: os 3 lugares onde você digita coisas

| Lugar | Como abrir | Serve para |
| --- | --- | --- |
| **Prompt de Comando** (tela preta) | Menu Iniciar → digite `cmd` | Digitar **comandos** (npm, npx, adb, gradlew) |
| **VS Code** (editor) | Menu Iniciar → Visual Studio Code | Escrever **código** (arquivos .ts, .tsx) |
| **Android Studio** | Menu Iniciar → Android Studio | Instalar o SDK e criar o **emulador** |

**Regra de ouro:** linhas que começam com `import`, `export`, `const` etc. são **código** — vão em arquivos no VS Code, nunca no Prompt. No Prompt só entram comandos (`npm install ...`, `npx expo start`, `adb devices`).

Caminho completo: Etapas 1–4 instalam as ferramentas (uma vez só) → Etapa 5 cria o emulador ou prepara o celular → Etapa 6 é o dia a dia (`npx expo start`) → Etapas 7–8 geram o APK → Etapa 9 instala no aparelho.

## Parte A — Instalação (faz uma vez só)

### Etapa 1 — Java (JDK 17)

**Por quê:** o Android só compila com Java 17.

1. Abra o Prompt **como administrador**.
2. `winget install Microsoft.OpenJDK.17`
3. Espere terminar, **feche e abra o Prompt de novo** (necessário sempre que instalar algo).

**Verificação:** `java -version` mostra `openjdk version "17...`.

### Etapa 2 — Android Studio (traz o SDK junto)

**Por quê:** instala o **SDK Android** (ferramentas de compilação) e o **emulador**.

1. Baixe em <https://developer.android.com/studio> e instale (tipo **Standard**), aceite as licenças e aguarde os downloads.
2. Na tela inicial: **More Actions → SDK Manager**.
3. Aba **SDK Platforms**: marque **Android 16 ("Baklava") — API 36** → Apply.
4. Aba **SDK Tools**: confirme **Android SDK Build-Tools**, **Android Emulator** e **Android SDK Platform-Tools**.

**Verificação:** o topo da tela mostra o caminho do SDK (ex.: `C:\Users\mobile\AppData\Local\Android\Sdk`) — **anote esse caminho**.

### Etapa 3 — Variáveis de ambiente

**Por quê:** é o que faz o `adb` (ponte PC ↔ Android) funcionar no Prompt.

1. Menu Iniciar → digite **"variáveis"** → **"Editar as variáveis de ambiente da conta"**.
2. Em *Variáveis de usuário* → **Novo...**: nome `ANDROID_HOME`, valor `%LOCALAPPDATA%\Android\Sdk`.
3. Ainda em cima: **Path → Editar → Novo** → adicione `%LOCALAPPDATA%\Android\Sdk\platform-tools`.
4. OK em tudo. **Feche e abra o Prompt de novo.**

**Verificação:** `adb --version` mostra a versão. Se aparecer *"'adb' não é reconhecido"*: confira a linha do Path e abra um Prompt novo.

### Etapa 4 — Node.js

1. No Prompt (administrador): `winget install OpenJS.NodeJS.LTS`
2. Feche e abra o Prompt.

**Verificação:** `node -v` mostra a versão (ex.: `v22...`).

> Não existe "instalar o Expo CLI" separado: ele roda com `npx expo ...` de dentro da pasta do projeto.

## Parte B — Onde o app vai rodar (escolha um dos dois)

### Etapa 5A — Criar o emulador (celular virtual)

1. Android Studio → **More Actions → Virtual Device Manager** → **Create virtual device**.
2. Escolha um aparelho (ex.: **Pixel 7**) → Next → imagem do **API 36** → Next → Finish.
3. Clique no botão **Play** ao lado do aparelho criado.

**Verificação:** abre uma janela com um Android funcionando — **deixe aberta**. Se travar/não abrir: a virtualização (Intel VT-x / AMD-V) pode estar desligada no BIOS.

### Etapa 5B — OU preparar o celular físico

1. No celular: **Configurações → Sobre o telefone** → toque **7 vezes** em "Número da versão" (libera o modo desenvolvedor).
2. Em **Opções do desenvolvedor**, ligue **Depuração USB**.
3. Conecte no PC via cabo USB e responda **Permitir** à pergunta *"Permitir depuração USB?"*.

**Verificação:** `adb devices` lista o aparelho com `device` ao lado. `unauthorized` = a permissão está esperando resposta na tela do celular.

## Parte C — Rodar o app (o dia a dia)

### Etapa 6 — Iniciar com o Expo

*(O projeto já existe em `C:\Users\mobile\sps_mobile` — para criar outro: `npx create-expo-app@latest nome-do-app`.)*

```bat
cd C:\Users\mobile\sps_mobile
npx expo start
```

Aparece um QR code e um menu de teclas:

- **Emulador aberto** ou **celular no cabo USB** → aperte a tecla **a** (o Expo instala e abre o app sozinho);
- **Celular sem cabo (mesmo Wi-Fi)** → instale o **Expo Go** na Play Store e escaneie o QR code.

**Verificação:** o app abre; ao **salvar** um arquivo no VS Code, a tela atualiza sozinha. Parar: `Ctrl + C`.

> **App não conecta na API?** Com Django local, o app **não enxerga** `localhost`. Em `src/api/config.ts` use `http://10.0.2.2:8000/api` (emulador) ou `http://IP-DO-PC:8000/api` (celular físico — `ipconfig` mostra o IP), e inicie o Django com `python manage.py runserver 0.0.0.0:8000` (ver [setup do servidor](guia-servidor-django.md)). Apontando para `https://mobile-sps.site/api` (produção), funciona direto.

## Parte D — Gerar o APK

### Etapa 7 — Gerar a pasta nativa `android`

**Por quê:** o projeto Expo é só JavaScript; este comando gera o projeto Android "de verdade" que o Gradle compila.

```bat
cd C:\Users\mobile\sps_mobile
npx expo prebuild -p android
```

**Verificação:** apareceu a pasta `android` dentro do projeto (`dir` para conferir).

### Etapa 8 — Compilar o APK

```bat
cd android
gradlew assembleRelease
```

A **primeira vez demora** (10–20 min — o Gradle baixa tudo); as próximas são rápidas.

**Verificação:** termina com `BUILD SUCCESSFUL` e existe o arquivo
`C:\Users\mobile\sps_mobile\android\app\build\outputs\apk\release\app-release.apk`.
Erro de Java/JDK → `java -version` tem que ser 17 (Etapa 1).

> **Assinatura:** esse APK sai assinado com a chave *debug* — perfeito para testar e distribuir internamente. Para publicar na Play Store será preciso criar uma keystore própria (passo rápido, para quando chegar lá).

## Parte E — Instalar o APK

### Etapa 9 — Colocar o APK no aparelho

- **Emulador:** arraste o `app-release.apk` para dentro da janela do emulador.
- **Celular pelo cabo:** `adb install C:\Users\mobile\sps_mobile\android\app\build\outputs\apk\release\app-release.apk`
- **Celular sem cabo:** envie o APK por WhatsApp/Drive, abra no celular e toque em Instalar (autorize "fontes desconhecidas" se pedir).

**Verificação:** o ícone do app aparece e abre **sem** o Expo rodando no PC.

## Resumo de comandos

```bat
:: rodar no dia a dia
cd C:\Users\mobile\sps_mobile
npx expo start          & :: tecla "a" abre no emulador/celular

:: gerar o APK
npx expo prebuild -p android
cd android
gradlew assembleRelease

:: instalar
adb install android\app\build\outputs\apk\release\app-release.apk
```

## Solução de problemas — erros comuns

1. **"'adb' não é reconhecido"** → variáveis de ambiente (Etapa 3) + abrir um Prompt novo.
2. **"'import' não é reconhecido"** → você digitou código no Prompt; código vai em arquivo no VS Code.
3. **Emulador não abre** → virtualização desligada no BIOS (VT-x/AMD-V).
4. **`gradlew` reclama de Java** → `java -version` precisa mostrar 17.
5. **App abre mas API não responde** → `localhost` não existe dentro do Android; use `10.0.2.2` (emulador) ou o IP do PC (celular); Django rodando com `runserver 0.0.0.0:8000`.
6. **Celular não aparece no `adb devices`** → depuração USB desligada, ou a permissão esperando na tela do celular.

---

*Padronizado em 2026-09-01. Fonte: documento "GUIA_EXPO_ANDROID_APK" (docx).*
