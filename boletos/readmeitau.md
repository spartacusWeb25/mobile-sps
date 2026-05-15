home
catálogo de soluções
Bolecode Pix
Bolecode Pix
versão: 1.0.4
como começar
tutorial de documentação
sobre a API

para quem é esta API?

restrições de uso

conhecimentos técnicos necessários

quais necessidades que essa API ajuda a resolver?

tempo aproximado para integração

sobre a API
Certificados nas Rotas das Nossas APIs
Atualmente, expomos nossas APIs por meio de duas rotas principais:
Modelo antigo:
https://secure.api.itau/...
Modelo novo:
https://pix-pj.itau.com/...
É importante identificar qual rota está sendo utilizada em sua integração, pois isso determina qual certificado deve ser confiado, caso seja necessário realizar essa configuração manualmente.
Confiar nos Certificados das APIs
Para consumir as APIs PIX do Itaú, é necessário confiar no certificado digital correspondente à rota utilizada.
Na maioria dos casos, essa confiança é gerenciada automaticamente por sistemas operacionais, servidores e linguagens de programação. Contudo, em alguns cenários, pode ser necessário adicionar manualmente o certificado raiz ao ambiente de desenvolvimento ou ao servidor, garantindo o funcionamento adequado das conexões SSL/TLS.
Modelo Antigo — secure.api.itau
Caso você esteja consumindo APIs que utilizam a rota secure.api.itau, pode ser necessário confiar manualmente no certificado raiz da GlobalSign.
Essa rota utiliza a autoridade certificadora (CA)
“GlobalSign Extended Validation CA – SHA256 – G3”.
O certificado raiz correspondente é o “GlobalSign Root R3”, disponível em:
https://support.globalsign.com/ca-certificates/globalsign-root-certificates

Modelo Novo — pix-pj.itau.com
Caso você esteja consumindo APIs que utilizam a rota pix-pj.itau.com, pode ser necessário confiar manualmente no certificado raiz da Amazon.
Essa rota utiliza a CA
“Amazon RSA 2048 M04”.
O certificado raiz correspondente é o “Amazon Root CA 1”, disponível em:
https://www.amazontrust.com/repository/AmazonRootCA1.pem

Bolecode: Solução de Recebimento
O Bolecode é uma solução que combina os dois principais meios de recebimento: PIX QR Code e Boleto, oferecendo aos clientes duas opções de pagamento em uma única emissão.

PIX QR Code
Instantaneidade: O pagamento é realizado de forma instantânea, sem necessidade de período de compensação.
Agilidade: O sistema integrado permite um controle ativo dos pagamentos, facilitando a baixa das pendências.
Facilidade: A emissão e conciliação estão disponíveis em todos os canais, como bankline, aplicativo, arquivo e API.
Boleto
Eficiência: Em caso de inadimplência, sua empresa pode realizar a negativação e o protesto para cobrar a dívida.
Praticidade: Permite visualizar as cobranças associadas ao CNPJ através do DDA (Débito Direto Autorizado).
Conveniência para o cliente: Oferece a possibilidade de pagamento presencial em caixas eletrônicos e Corban, proporcionando mais flexibilidade e comodidade, oferecendo mais opções no processo de pagamento.
Informações para Emissão de Bolecode/Código de Barras de Cobrança Itaú
Mantenha a guarda dos documentos comprobatórios que dão origem aos boletos emitidos por 10 anos, pois poderão ser solicitados a qualquer momento.
Garanta que os dados constantes no registro do boleto e no contrato de venda do produto ou serviço a que se refere o boleto emitido estejam corretos.
O CPF e/ou CNPJ do pagador e beneficiário final indicado deve constar como ativo/regular na Receita Federal.
Para endereço, a responsabilidade do dado estar correto é do cliente. O Itaú valida se estão preenchidos com algum caracter: logradouro, bairro e cidade; CEP com 8 números e informado uma Unidade Federativa.
Atenção: Para que os serviços de negativação expressa, protesto, cálculo de encargos em dias úteis sejam efetivados, o endereço deve estar conforme consta no site dos Correios.

Conceitos e Figuras do Boleto
Beneficiário: Emissor do boleto e beneficiário dos recursos oriundos do pagamento do boleto quando a cobrança não for emitida por meio do terceiro habilitador.

Pagador: Quem deverá realizar o pagamento do boleto.

Sacador Avalista (atual Beneficiário Final): Figura que receberá o crédito referente ao pagamento do boleto devido à prestação de serviço ou venda de produto ao pagador. O preenchimento deste campo no boleto deve ser realizado apenas nos casos em que o Beneficiário figura como Terceiro Habilitador.

Terceiro Habilitador: Beneficiário que emite boletos para viabilizar o recebimento de recursos através do pagamento de boletos para outras pessoas/empresas.

Atenção!
Sacador Avalista: Essa figura deixou de existir desde a vigência da Circular nº 3.956 do Banco Central do Brasil. Ao emitir o boleto, atenção para indicar as figuras corretas. Nesta documentação, todos os campos que citarem o sacador avalista devem ser considerados como Sacador Avalista (atual Beneficiário Final). Estamos ajustando o termo sistemicamente e, em breve, será atualizado.

Beneficiário: O Beneficiário não deve ser o Pagador e nem o Beneficiário final.

Pagador: O pagador é igual ao Beneficiário Final quando a espécie do boleto for Boleto Depósito Aporte. Nas demais espécies, caso tenha um beneficiário final, será uma terceira pessoa/empresa.

Webhook para parceiros Pix (disponível apenas para parceiros)
O webhook de parceiros é uma solução que busca automatizar o processo de compartilhamento de credenciais do cliente recebedor para um parceiro homologado do Itaú para utilização do QR Code do Pix.

Para que o webhook funcione, é necessário que o cliente desenvolva uma API de callback através de uma URL exposta na web que possua uma camada de autenticação mTLS (HTTPS).

Com essa integração, o parceiro estará apto a receber automaticamente as credenciais do cliente quando o cliente recebedor realizar o consentimento diretamente nos canais digitais do Itaú.

para quem é esta API?
Bolecode (disponível apenas para clientes)

O Bolecode é indicado aos clientes que já emitem boletos, mas desejam adicionar QR Code Pix para ampliar as formas de recebimento.
Os principais casos de uso atualmente são:

*Cobranças com recorrências (universidades, escolas, condomínios etc.).
*Lojas virtuais (e-commerce).

Webhook para parceiros Pix (disponível apenas para parceiros)

O webhook de parceiros é uma solução que busca automatizar o processo de compartilhamento de credenciais do cliente recebedor para um parceiro homologado do Itaú para utilização do QR Code do Pix.

Os principais casos de uso atualmente são:

Automações comerciais;
TEF Houses;
Software houses;
Gateways e plataformas de e-commerce.
restrições de uso
Para utilização de todas as APIs, é necessário estar habilitado no Portal Itaú for Developers e possuir um certificado dinâmico ativado.

Para utilização do webhook é necessário possuir um certificado mTLS e uma API Call Back.

conhecimentos técnicos necessários
Conhecimentos prévios necessários:

Conhecimentos técnicos

Construção de APIs REST escaláveis Comunicações assíncronas e síncronas Padrões de autenticação

Padrões de segurança

Tecnologias

API REST/Restful HTTP/HTTPS JSON Postman/Insomnia mTls OAUTH2

HTTP JSON Postman

quais necessidades que essa API ajuda a resolver?
Com as APIs de Bolecode, o cliente pode realizar a emissão de um bolecode associado a um QR Code do Pix.

Com as APIs do webhook o parceiro pode cadastrar uma URL (API Call Back) para automatizar o processo de recebimento de credenciais do cliente recebedor para utilização do QR Code do Pix.

tempo aproximado para integração
15 dias: essa é a média de tempo que um desenvolvedor pode levar para preparar toda a integração com essa API. Isso pode variar de acordo com o tamanho do time e experiência dos desenvolvedores envolvidos.
