# --- ABA 2: ALERTAS (REESTRUTURADA COM FILTROS E CONFIRMAÇÃO MANUAL) ---
elif st.session_state.aba_atual == "🚨 Alertas":
    st.subheader("🚨 Radar de Clientes Pendentes")
    
    # Inicializa variáveis de controle de fluxo se não existirem
    if "clientes_processados_aguardando" not in st.session_state:
        st.session_state.clientes_processados_aguardando = []
    
    # 1. EXIBE A CAIXA DO SUPERVISOR CASO JÁ TENHA TEXTO GERADO
    if st.session_state.texto_supervisor_gerado:
        with st.expander("📋 RELATÓRIO DO SUPERVISOR GERADO", expanded=True):
            st.text_area("Texto estruturado:", value=st.session_state.texto_supervisor_gerado, height=200, key="txt_sup_area_fix")
            
            texto_js_safe = json.dumps(st.session_state.texto_supervisor_gerado)
            html_button_js = f"""
            <button id=\"copyBtn\" style=\"width: 100%; background-color: #00875A; color: white; border: none; padding: 14px; border-radius: 6px; font-weight: bold; font-size: 16px; cursor: pointer;\">📋 Copiar Relatório</button>
            <script>
            document.getElementById('copyBtn').addEventListener('click', function() {{
                const text = {texto_js_safe};
                navigator.clipboard.writeText(text);
                this.innerText = '✅ Copiado com sucesso!';
                setTimeout(() => {{ this.innerText = '📋 Copiar Relatório'; }}, 2000);
            }});
            </script>
            """
            components.html(html_button_js, height=55)
            
            # BOTÃO DE CONFIRMAÇÃO MANUAL: Aqui sim aplicamos a tag definitiva
            if st.button("💾 Marcar Selecionados como Reportados"):
                for c_nome in st.session_state.clientes_processados_aguardando:
                    st.session_state.enviados_supervisor_mes.add(c_nome)
                    # Desmarca o checkbox para a próxima rodada
                    if f"chk_{c_nome}" in st.session_state:
                        st.session_state[f"chk_{c_nome}"] = False
                
                # Limpa a fila temporária e o texto
                st.session_state.clientes_processados_aguardando = []
                st.session_state.texto_supervisor_gerado = ""
                salvar_progresso_atual()
                st.toast("Clientes marcados como reportados com sucesso!", icon="💾")
                st.rerun()
            st.write("---")

    # 2. SEÇÃO DE FILTROS DA LISTA
    st.markdown("### Filtros da Lista")
    filtro_status = st.selectbox(
        "Filtrar por status de envio:",
        ["Mostrar todos", "Apenas Não Reportados", "Apenas Reportados"]
    )
    
    busca_alerta = st.text_input("🔍 Buscar Cliente em Alerta:", placeholder="Digite o nome...").strip()

    # 3. MONTAGEM DA LISTA DE DADOS
    lista_alertas = []
    for cli, dados in dict_carteira.items():
        if pd.isna(cli) or str(cli).lower() == 'nan' or dados["dias"] <= 0:
            continue
        if "SUMIDO" in dados["tags"] or "NÃO POSITIVADO" in dados["tags"]:
            # Verifica se já está reportado no mês
            ja_reportado = cli in st.session_state.enviados_supervisor_mes
            
            # Aplicação do Filtro de Status
            if filtro_status == "Apenas Não Reportados" and ja_reportado:
                continue
            if filtro_status == "Apenas Reportados" and not ja_reportado:
                continue
                
            lista_alertas.append({"Cliente": cli, "Dias": dados["dias"], "Tags": dados["tags"], "Reportado": ja_reportado})
            
    df_alertas_visuais = pd.DataFrame(lista_alertas)
    if not df_alertas_visuais.empty:
        df_alertas_visuais = df_alertas_visuais.sort_values(by="Dias", ascending=False)
        
    # Aplicação do Filtro de Busca por Texto
    if busca_alerta and not df_alertas_visuais.empty:
        termo_limpo = limpar_texto(busca_alerta)
        df_alertas_visuais = df_alertas_visuais[df_alertas_visuais['Cliente'].apply(lambda x: termo_limpo in limpar_texto(x))]
    
    # 4. RENDERIZAÇÃO DOS CHECKBOXES
    if df_alertas_visuais.empty:
        st.info("Nenhum cliente localizado para os filtros selecionados.")
    else:
        st.markdown(f"📊 Exibindo **{len(df_alertas_visuais)}** clientes nesta lista:")
        
        for idx, row in df_alertas_visuais.iterrows():
            c_nome = row["Cliente"]
            
            if f"chk_{c_nome}" not in st.session_state:
                st.session_state[f"chk_{c_nome}"] = False
            
            with st.container():
                st.checkbox(f"📍 {c_nome} ({row['Dias']} dias sem comprar)", key=f"chk_{c_nome}")
                
                html_badges = obter_badges_html(c_nome)
                if row["Reportado"]:
                    html_badges += '<span style="background-color:#FFC400; color:#111; padding:3px 5px; border-radius:4px; font-weight:bold; font-size:11px; margin-right:4px;">📅 JÁ REPORTADO</span>'
                st.markdown(html_badges, unsafe_allow_html=True)
                
                if st.button(f"🔍 Histórico de {c_nome[:12]}...", key=f"btn_h_{idx}"):
                    st.session_state.busca_direta_cliente = c_nome
                    st.session_state.sub_aba_consulta = "👤 Por Cliente"
                    st.session_state.aba_atual = "🔍 Consulta"  
                    st.rerun()
            st.write("---")
        
        # 5. BOTÃO FIXO PARA CONSTRUIR O TEXTO DO SUPERVISOR (SEM MARCAR COMO REPORTADO AINDA)
        st.write("")
        if st.button("⚡ GERAR RELATÓRIO DOS SELECIONADOS", type="primary"):
            novo_texto_acumulado = ""
            clientes_selecionados_na_rodada = []
            
            for idx, row in df_alertas_visuais.iterrows():
                c_nome = row["Cliente"]
                
                if st.session_state.get(f"chk_{c_nome}", False):
                    clientes_selecionados_na_rodada.append(c_nome)
                    status_txt = "Sumido" if row["Dias"] > 30 else "Pendente"
                    novo_texto_acumulado += f"📌 {c_nome} ({status_txt} - {row['Dias']} dias sem comprar)\n"
                    
                    # Regra dos Itens Mais Comprados
                    df_cli_h = df_total[df_total['Cliente'] == c_nome]
                    if not df_cli_h.empty:
                        top_itens = df_cli_h.groupby('Produto')['Faturamento Brut'].sum().nlargest(3).index.tolist()
                        novo_texto_acumulado += "   🔹 Mais Comprados pelo Cliente:\n"
                        for item in top_itens:
                            novo_texto_acumulado += f"      ▪️ {item}\n"
                    else:
                        novo_texto_acumulado += "   🔹 Sem histórico recente registrado\n"
                    
                    # Regra das Vendas Cruzadas
                    nome_limpo_cli = limpar_texto(c_nome)
                    sugestoes_seg = []
                    regras_segmento = {
                        "pizzaria": ["Calabresa", "Muçarela", "Presunto", "Molho de Tomate"], 
                        "pizza": ["Calabresa", "Muçarela", "Presunto"],
                        "lanches": ["Hambúrguer", "Batata Frita", "Cheddar", "Maionese"], 
                        "burguer": ["Hambúrguer", "Cheddar"],
                        "churrascaria": ["Linguiça", "Picanha", "Alcatra", "Carvão"], 
                        "churrasco": ["Linguiça", "Picanha", "Alcatra"]
                    }
                    for chave, itens_sugeridos in regras_segmento.items():
                        if chave in nome_limpo_cli: 
                            sugestoes_seg.extend(itens_sugeridos)
                    
                    if congest := list(set(sugestoes_seg)):
                        novo_texto_acumulado += "   💡 Oportunidades de Venda Cruzada:\n"
                        for sug in congest:
                            novo_texto_acumulado += f"      ▪️ {sug}\n"
                    novo_texto_acumulado += "\n"
            
            if len(clientes_selecionados_na_rodada) > 0:
                # Armazena o texto e a lista de quem deve receber a tag no clique manual
                st.session_state.texto_supervisor_gerado = novo_texto_acumulado
                st.session_state.clientes_processados_aguardando = clientes_selecionados_na_rodada
                st.toast(f"✅ Relatório pronto para conferência!", icon="🚀")
                st.rerun()
            else:
                st.warning("⚠️ Por favor, marque pelo menos um Checkbox na lista acima para poder gerar o texto!")
