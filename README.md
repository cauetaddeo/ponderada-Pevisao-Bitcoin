# Atividade Ponderada M7 — Predição do Bitcoin

Arquitetura planejada para estimar o fechamento do próximo dia do par BTC/USDT a partir dos sete fechamentos diários anteriores. Os diagramas representam o fluxo previsto para a implementação.

## Arquitetura e fluxo dos dados

```mermaid
flowchart TB
    cliente["Cliente no navegador<br/>Página HTML e JavaScript"]
    dados[("CSV histórico no host<br/>data/btc_usdt.csv")]
    artefatos[("Artefatos persistidos no host<br/>artifacts/model.joblib<br/>Metadados e métricas")]

    subgraph docker["Ambiente Docker — Docker Compose"]
        direction TB

        subgraph treinamento["Container de treinamento — Python"]
            preparar["Preparar dados<br/>Ordenar datas e criar janelas de 7 fechamentos"]
            treinar["Treinar e avaliar<br/>StandardScaler + Ridge<br/>Divisão cronológica entre treino e teste"]
            exportar["Exportar pipeline treinado<br/>Modelo e normalização no mesmo artefato"]
            preparar --> treinar --> exportar
        end

        subgraph inferencia["Container de inferência — Python / FastAPI"]
            carregar["Inicialização<br/>Carregar model.joblib uma vez"]
            api["Backend HTTP<br/>GET / — página cliente<br/>GET /health — serviço e modelo prontos<br/>POST /predict — predição"]
            carregar --> api
        end
    end

    dados -->|"Montagem de ./data: somente leitura"| preparar
    exportar -->|"Montagem de ./artifacts: escrita"| artefatos
    artefatos -->|"Montagem de ./artifacts: somente leitura"| carregar
    cliente -->|"HTTP: solicitar página, consultar saúde ou enviar 7 fechamentos"| api
    api -->|"Página HTML, status ou predição em JSON"| cliente
```

O treinamento será executado primeiro e encerrará após gerar os artefatos. A pasta `artifacts/` ficará disponível para os dois containers por meio de bind mounts: o treinamento escreverá nela e o backend terá acesso somente para leitura. Após o treinamento terminar com sucesso, o backend será iniciado para carregar o modelo.

A normalização será ajustada apenas com os dados de treino e exportada junto ao modelo. A inferência usará esse mesmo pipeline, preservando o processamento utilizado no treinamento.

## UML de sequência — treinamento e uso da aplicação

```mermaid
sequenceDiagram
    actor Usuario as Usuário
    participant Cliente as Cliente — navegador
    participant Treino as Container de treinamento
    participant CSV as CSV histórico no host
    participant Artefato as Artefatos no host
    participant API as Container de inferência — FastAPI

    Note over Treino,Artefato: Etapa 1 — treinamento antes da inicialização do backend
    Treino->>CSV: Ler datas e preços de fechamento
    CSV-->>Treino: Histórico diário BTC/USDT
    Treino->>Treino: Preparar janelas e separar treino e teste cronologicamente
    Treino->>Treino: Ajustar normalização, treinar e avaliar o modelo
    Treino->>Artefato: Salvar model.joblib, metadados e métricas
    Note over Treino: Encerrar após concluir a exportação

    Note over Artefato,API: Etapa 2 — inicialização do backend
    API->>Artefato: Ler model.joblib e metadados
    Artefato-->>API: Pipeline treinado e informações do modelo
    API->>API: Manter o pipeline carregado em memória

    Note over Usuario,API: Etapa 3 — interação com a aplicação
    Usuario->>Cliente: Abrir a aplicação
    Cliente->>API: GET /
    API-->>Cliente: Página HTML e JavaScript
    Cliente->>API: GET /health
    API-->>Cliente: JSON com serviço ativo e modelo carregado
    Usuario->>Cliente: Informar 7 fechamentos consecutivos em ordem cronológica
    Cliente->>API: POST /predict — histórico e data do último fechamento
    API->>API: Validar entrada e executar o pipeline carregado
    API-->>Cliente: JSON com preço estimado em USDT e data prevista
    Cliente-->>Usuario: Exibir a estimativa para o próximo dia
```

Uma solicitação de predição executará apenas a inferência com o modelo já carregado. O backend validará a quantidade de fechamentos e os valores recebidos. O endpoint `/health` indicará que o serviço está pronto para atender solicitações com o modelo disponível.

As estimativas serão experimentais e suas limitações serão documentadas no devlog.
